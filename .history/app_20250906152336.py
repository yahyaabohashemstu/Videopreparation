import os
import uuid
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import cv2  # اختياري (غير مستخدم مباشرةً، إبقاؤه لا يضر)
from moviepy.editor import VideoFileClip, ImageClip, CompositeVideoClip
from PIL import Image
import tempfile
import shutil
import subprocess
import json
from celery import Celery

app = Flask(__name__)
CORS(app)

# المتغيرات البيئية
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-here')
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', '/data/uploads')
app.config['OUTPUT_FOLDER'] = os.environ.get('OUTPUT_FOLDER', '/data/outputs')
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', 500 * 1024 * 1024))  # 500MB كحد أقصى

# إعداد Celery
def make_celery(app):
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    celery = Celery(app.import_name, backend=redis_url, broker=redis_url)
    celery.conf.update(app.config)
    
    class ContextTask(celery.Task):
        """Make celery tasks work with Flask app context."""
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery

celery = make_celery(app)

# إنشاء المجلدات المطلوبة
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# مسارات الملفات الثابتة
ASSETS_FOLDER = 'assets'
WATERMARK_PATH = os.path.join(ASSETS_FOLDER, 'watermark.png')
OUTRO_PATH = os.path.join(ASSETS_FOLDER, 'outro.mp4')

# الامتدادات المسموح بها
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv'}
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}

def allowed_file(filename, allowed_extensions):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def get_video_info(video_path):
    """الحصول على معلومات الفيديو باستخدام FFprobe"""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            info = json.loads(result.stdout)
            return info
    except Exception as e:
        print(f"خطأ في الحصول على معلومات الفيديو: {e}")
    return None

def get_nvenc_encoder():
    """
    تحديد الـ NVENC المتوفر: يفضّل HEVC وإن لم يتوفر يستخدم H.264.
    يعاد 'hevc_nvenc' أو 'h264_nvenc' أو None إذا غير مدعوم.
    """
    try:
        res = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True)
        if res.returncode != 0:
            return None
        encs = res.stdout
        if 'hevc_nvenc' in encs:
            return 'hevc_nvenc'
        if 'h264_nvenc' in encs:
            return 'h264_nvenc'
        return None
    except Exception:
        return None

def test_gpu_support():
    """اختبار وجود FFmpeg ووجود دعم NVENC"""
    try:
        # اختبار FFmpeg
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ FFmpeg غير مثبت أو غير متاح")
            return False

        print("✅ FFmpeg مثبت ويعمل")

        encoder = get_nvenc_encoder()
        if encoder:
            print(f"✅ NVENC مدعوم ({encoder}) - يمكن استخدام GPU!")
            return True
        else:
            print("❌ NVENC غير مدعوم - سيتم استخدام CPU")
            return False

    except Exception as e:
        print(f"❌ خطأ في اختبار GPU: {e}")
        return False

def get_ultra_fast_settings():
    """إعدادات NVENC فائقة السرعة للمعالجة السريعة"""
    return [
        '-preset', 'p1',           # أسرع preset ممكن (p1 = fastest)
        '-tune', 'll',             # Low Latency للسرعة القصوى
        '-rc', 'cbr',              # Constant bitrate للسرعة
        '-cq', '25',               # جودة أقل للسرعة (25 بدل 18)
        '-b:v', '4M',              # معدل بت أقل للسرعة
        '-maxrate', '6M',          # أقصى معدل بت أقل
        '-bufsize', '8M',          # بفر أصغر للسرعة
        '-gpu', '0',               # استخدام أول GPU
        '-2pass', '0',             # تعطيل 2-pass للسرعة
    ]

def process_video_ffmpeg_gpu(video_path, output_path):
    """معالجة الفيديو باستخدام FFmpeg مع تسريع GPU (NVENC)"""
    temp_watermark_path = None
    temp_outro_path = None
    temp_watermarked_path = None

    try:
        encoder = get_nvenc_encoder()
        if not encoder:
            print("NVENC غير متوفر، لا يمكن استخدام معالجة GPU.")
            return False

        # معلومات الفيديوهات
        video_info = get_video_info(video_path)
        outro_info = get_video_info(OUTRO_PATH)
        if not video_info or not outro_info:
            return False

        video_stream = next((s for s in video_info['streams'] if s['codec_type'] == 'video'), None)
        outro_stream = next((s for s in outro_info['streams'] if s['codec_type'] == 'video'), None)
        if not video_stream or not outro_stream:
            return False

        width = int(video_stream['width'])
        height = int(video_stream['height'])
        duration = float(video_info['format']['duration'])
        video_has_audio = any(s['codec_type'] == 'audio' for s in video_info['streams'])
        outro_has_audio = any(s['codec_type'] == 'audio' for s in outro_info['streams'])

        print(f"معالجة فيديو: {width}x{height}, المدة: {duration:.2f} ثانية")
        print(f"الفيديو الرئيسي يحتوي على صوت: {video_has_audio}")
        print(f"الأوترو يحتوي على صوت: {outro_has_audio}")

        # 1) تحضير صورة العلامة المائية بشفافية 30% وبنفس أبعاد الفيديو
        temp_watermark = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        temp_watermark_path = temp_watermark.name
        temp_watermark.close()

        with Image.open(WATERMARK_PATH) as img:
            img = img.resize((width, height), Image.Resampling.LANCZOS)
            # ضبط ألفا 30%:
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            r, g, b, a = img.split()
            # تعيين ألفا ثابت 30% عبر الصورة كلها
            a = a.point(lambda x: int(255 * 0.3))
            img = Image.merge('RGBA', (r, g, b, a))
            img.save(temp_watermark_path, 'PNG')

        print("تم تحضير العلامة المائية")

        # 2) تحضير الأوترو بنفس أبعاد الفيديو
        temp_outro = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
        temp_outro_path = temp_outro.name
        temp_outro.close()

        outro_cmd = [
            'ffmpeg', '-y', '-i', OUTRO_PATH,
            '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,'
                   f'pad={width}:{height}:(ow-iw)/2:(oh-ih)/2',
            '-c:v', encoder
        ]
        outro_cmd.extend(get_rtx_4060_settings())
        if outro_has_audio:
            outro_cmd.extend(['-c:a', 'aac', '-b:a', '128k'])
        else:
            outro_cmd.extend(['-an'])
        outro_cmd.append(temp_outro_path)

        print("معالجة الأوترو...")
        print(f"أمر الأوترو: {' '.join(outro_cmd)}")
        result = subprocess.run(outro_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"خطأ في معالجة الأوترو: {result.stderr}")
            return False

        # 3) إضافة العلامة المائية على الفيديو الأصلي
        temp_watermarked = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
        temp_watermarked_path = temp_watermarked.name
        temp_watermarked.close()

        watermark_cmd = [
            'ffmpeg', '-y', '-i', video_path, '-i', temp_watermark_path,
            '-filter_complex', f'[0:v][1:v]overlay=0:0:format=auto,format=yuv420p',
            '-c:v', encoder
        ]
        watermark_cmd.extend(get_rtx_4060_settings())
        if video_has_audio:
            watermark_cmd.extend(['-c:a', 'copy'])
        else:
            watermark_cmd.extend(['-an'])
        watermark_cmd.append(temp_watermarked_path)

        print("دمج الفيديو مع العلامة المائية...")
        print(f"أمر العلامة المائية: {' '.join(watermark_cmd)}")
        result = subprocess.run(watermark_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"خطأ في دمج العلامة المائية: {result.stderr}")
            return False

        # 4) دمج الفيديو المعلّم + الأوترو (مع مراعاة الصوت)
        if video_has_audio and outro_has_audio:
            filter_complex = '[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[outv][outa]'
            map_args = ['-map', '[outv]', '-map', '[outa]']
            audio_codec = ['-c:a', 'aac', '-b:a', '128k']
        elif video_has_audio and not outro_has_audio:
            filter_complex = '[0:v][0:a][1:v]concat=n=2:v=1:a=1[outv][outa]'
            map_args = ['-map', '[outv]', '-map', '[outa]']
            audio_codec = ['-c:a', 'copy']
        elif not video_has_audio and outro_has_audio:
            # توليد مسار صوتي صامت للفيديو الأول ليتوافق الدمج
            filter_complex = ('anullsrc=channel_layout=stereo:sample_rate=48000[a0];'
                              '[0:v][a0][1:v][1:a]concat=n=2:v=1:a=1[outv][outa]')
            map_args = ['-map', '[outv]', '-map', '[outa]']
            audio_codec = ['-c:a', 'aac', '-b:a', '128k']
        else:
            filter_complex = '[0:v][1:v]concat=n=2:v=1[outv]'
            map_args = ['-map', '[outv]']
            audio_codec = ['-an']

        final_cmd = [
            'ffmpeg', '-y',
            '-i', temp_watermarked_path,
            '-i', temp_outro_path,
            '-filter_complex', filter_complex
        ]
        final_cmd.extend(map_args)
        final_cmd.extend(['-c:v', encoder])
        final_cmd.extend(get_rtx_4060_settings())
        final_cmd.extend(audio_codec)
        final_cmd.extend(['-movflags', '+faststart'])
        final_cmd.append(output_path)

        print("دمج الفيديو النهائي...")
        print(f"أمر الدمج النهائي: {' '.join(final_cmd)}")
        result = subprocess.run(final_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"خطأ في الدمج النهائي: {result.stderr}")
            return False

        # تنظيف الملفات المؤقتة
        for p in [temp_watermark_path, temp_outro_path, temp_watermarked_path]:
            try:
                if p and os.path.exists(p):
                    os.unlink(p)
            except Exception:
                pass

        print("✅ تمت المعالجة بنجاح باستخدام GPU!")
        return True

    except Exception as e:
        print(f"خطأ في معالجة الفيديو باستخدام FFmpeg GPU: {str(e)}")
        for temp_file in [temp_watermark_path, temp_outro_path, temp_watermarked_path]:
            try:
                if temp_file and os.path.exists(temp_file):
                    os.unlink(temp_file)
            except Exception:
                pass
        return False

def process_video_fallback(video_path, output_path):
    """معالجة بديلة باستخدام MoviePy (CPU)"""
    try:
        # تحميل المقاطع
        video = VideoFileClip(video_path)
        watermark = ImageClip(WATERMARK_PATH).resize((video.w, video.h)).set_opacity(0.3)
        outro = VideoFileClip(OUTRO_PATH).resize((video.w, video.h))

        # وضع العلامة المائية طوال مدة الفيديو
        wm_layer = watermark.set_position('center').set_duration(video.duration)
        video_with_watermark = CompositeVideoClip([video, wm_layer])

        # دمج الأوترو بعد نهاية الفيديو
        final_timeline = CompositeVideoClip([
            video_with_watermark.set_duration(video.duration),
            outro.set_position('center').set_start(video.duration)
        ])

        # حفظ الناتج بإعدادات سريعة
        final_timeline.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            threads=8,
            preset='ultrafast',
            verbose=False,
            logger=None
        )

        # تنظيف الذاكرة
        video.close()
        outro.close()
        final_timeline.close()
        return True

    except Exception as e:
        print(f"خطأ في معالجة الفيديو باستخدام MoviePy: {str(e)}")
        return False

def merge_videos(video1_path, video2_path):
    """دمج فيديوهين معاً باستخدام FFmpeg"""
    try:
        # إنشاء ملف مؤقت للفيديو المدموج
        merged_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
        merged_path = merged_file.name
        merged_file.close()

        # أمر FFmpeg لدمج الفيديوهات
        merge_cmd = [
            'ffmpeg', '-y',
            '-i', video1_path,
            '-i', video2_path,
            '-filter_complex', '[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[outv][outa]',
            '-map', '[outv]',
            '-map', '[outa]',
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-preset', 'medium',
            merged_path
        ]

        print(f"أمر دمج الفيديوهات: {' '.join(merge_cmd)}")
        result = subprocess.run(merge_cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ تم دمج الفيديوهات بنجاح")
            return merged_path
        else:
            print(f"❌ خطأ في دمج الفيديوهات: {result.stderr}")
            # حذف الملف المؤقت في حالة الفشل
            try:
                os.unlink(merged_path)
            except:
                pass
            return None

    except Exception as e:
        print(f"❌ خطأ في دالة دمج الفيديوهات: {str(e)}")
        return None

@celery.task(bind=True)
def process_video_task(self, video_path, output_path, video2_path=None):
    """مهمة Celery لمعالجة الفيديو"""
    try:
        # تحديث حالة المهمة
        self.update_state(state='PROCESSING', meta={'progress': 10, 'status': 'بدء المعالجة...'})
        
        print("🔍 اختبار دعم GPU...")
        gpu_supported = test_gpu_support()
        
        # تحديث التقدم
        self.update_state(state='PROCESSING', meta={'progress': 20, 'status': 'فحص دعم GPU...'})

        # دمج الفيديوهات إذا كان هناك فيديو ثاني
        final_video_path = video_path
        if video2_path:
            print("🔗 دمج الفيديوهات...")
            self.update_state(state='PROCESSING', meta={'progress': 30, 'status': 'دمج الفيديوهات...'})
            merged_path = merge_videos(video_path, video2_path)
            if merged_path:
                final_video_path = merged_path
            else:
                print("⚠️ فشل دمج الفيديوهات، استخدام الفيديو الأول فقط")

        # تحديث التقدم
        self.update_state(state='PROCESSING', meta={'progress': 50, 'status': 'معالجة الفيديو...'})

        if gpu_supported:
            print("🚀 استخدام GPU (NVENC)...")
            self.update_state(state='PROCESSING', meta={'progress': 60, 'status': 'معالجة بـ GPU...'})
            if process_video_ffmpeg_gpu(final_video_path, output_path):
                # تنظيف الملف المدموج المؤقت إذا كان موجوداً
                if video2_path and final_video_path != video_path:
                    try:
                        os.unlink(final_video_path)
                        print("🧹 تم تنظيف الملف المدموج المؤقت")
                    except:
                        pass
                
                self.update_state(state='SUCCESS', meta={'progress': 100, 'status': 'تمت المعالجة بنجاح!'})
                return {'status': 'completed', 'output_path': output_path}
            else:
                print("⚠️ فشل GPU، الانتقال إلى CPU...")

        print("🖥️ استخدام MoviePy (CPU) كبديل...")
        self.update_state(state='PROCESSING', meta={'progress': 70, 'status': 'معالجة بـ CPU...'})
        result = process_video_fallback(final_video_path, output_path)
        
        # تنظيف الملف المدموج المؤقت إذا كان موجوداً
        if video2_path and final_video_path != video_path:
            try:
                os.unlink(final_video_path)
                print("🧹 تم تنظيف الملف المدموج المؤقت")
            except:
                pass
        
        if result:
            self.update_state(state='SUCCESS', meta={'progress': 100, 'status': 'تمت المعالجة بنجاح!'})
            return {'status': 'completed', 'output_path': output_path}
        else:
            raise Exception("فشل في معالجة الفيديو")

    except Exception as e:
        print(f"❌ خطأ عام في المعالجة: {str(e)}")
        self.update_state(state='FAILURE', meta={'progress': 0, 'status': f'خطأ: {str(e)}'})
        raise

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_video():
    try:
        # تحقق من وجود ملف الفيديو الأول
        if 'video' not in request.files:
            return jsonify({'error': 'ملف الفيديو الأول مطلوب'}), 400

        video_file = request.files['video']
        video2_file = request.files.get('video2')  # الفيديو الثاني اختياري

        # تحقق من اسم الملف الأول
        if video_file.filename == '':
            return jsonify({'error': 'يرجى اختيار ملف الفيديو الأول'}), 400

        # تحقق من امتداد الفيديو الأول
        if not allowed_file(video_file.filename, ALLOWED_EXTENSIONS):
            return jsonify({'error': 'صيغة الفيديو الأول غير مدعومة'}), 400
            
        # تحقق من الفيديو الثاني إذا كان موجوداً
        has_second_video = video2_file and video2_file.filename != ''
        if has_second_video:
            if not allowed_file(video2_file.filename, ALLOWED_EXTENSIONS):
                return jsonify({'error': 'صيغة الفيديو الثاني غير مدعومة'}), 400
            
        # تحقق من وجود الملفات الثابتة
        if not os.path.exists(WATERMARK_PATH):
            return jsonify({'error': 'العلامة المائية غير موجودة'}), 500
        if not os.path.exists(OUTRO_PATH):
            return jsonify({'error': 'الأوترو غير موجود'}), 500

        # مشروع مؤقت بمعرف فريد
        project_id = str(uuid.uuid4())
        project_folder = os.path.join(app.config['UPLOAD_FOLDER'], project_id)
        os.makedirs(project_folder, exist_ok=True)

        # حفظ ملف الفيديو الأول
        video_path = os.path.join(project_folder, secure_filename(video_file.filename))
        video_file.save(video_path)
        
        # حفظ ملف الفيديو الثاني إذا كان موجوداً
        video2_path = None
        if has_second_video:
            video2_path = os.path.join(project_folder, secure_filename(video2_file.filename))
            video2_file.save(video2_path)

        # ناتج المعالجة
        output_filename = f"output_{project_id}.mp4"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)

        # بدء مهمة Celery
        task = process_video_task.apply_async(args=[video_path, output_path, video2_path])
        
        return jsonify({
            'success': True,
            'job_id': task.id,
            'status': 'queued',
            'message': 'تم بدء معالجة الفيديو',
            'output_filename': output_filename
        })

    except Exception as e:
        return jsonify({'error': f'خطأ في الخادم: {str(e)}'}), 500

@app.route('/status/<task_id>')
def task_status(task_id):
    """تتبع حالة مهمة معالجة الفيديو"""
    try:
        task = process_video_task.AsyncResult(task_id)
        
        if task.state == 'PENDING':
            response = {
                'state': task.state,
                'status': 'في الانتظار...',
                'progress': 0
            }
        elif task.state == 'PROCESSING':
            response = {
                'state': task.state,
                'status': task.info.get('status', 'جاري المعالجة...'),
                'progress': task.info.get('progress', 0)
            }
        elif task.state == 'SUCCESS':
            response = {
                'state': task.state,
                'status': 'تمت المعالجة بنجاح!',
                'progress': 100,
                'result': task.info
            }
        else:  # FAILURE
            response = {
                'state': task.state,
                'status': task.info.get('status', 'حدث خطأ في المعالجة'),
                'progress': 0,
                'error': str(task.info)
            }
        
        return jsonify(response)
    
    except Exception as e:
        return jsonify({'error': f'خطأ في استعلام الحالة: {str(e)}'}), 500

@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_file(
            os.path.join(app.config['OUTPUT_FOLDER'], filename),
            as_attachment=True,
            download_name=filename
        )
    except Exception:
        return jsonify({'error': 'ملف غير موجود'}), 404

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy'})

@app.route('/test-gpu')
def test_gpu():
    """نقطة فحص دعم GPU"""
    try:
        gpu_supported = test_gpu_support()
        return jsonify({
            'gpu_supported': gpu_supported,
            'message': 'GPU مدعوم' if gpu_supported else 'GPU غير مدعوم'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 بدء تشغيل التطبيق...")
    print("🔍 اختبار دعم GPU عند الإقلاع:")
    test_gpu_support()
    print("🟢 تشغيل الخادم Flask...")
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("DEBUG", "False").lower() == "true"
    app.run(debug=debug_mode, host="0.0.0.0", port=port)
