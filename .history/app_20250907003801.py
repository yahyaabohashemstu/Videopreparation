import os
import uuid
import sys
import traceback
import logging
import datetime
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
    
    # إعدادات Redis محسنة للاتصال
    celery_config = {
        'broker_url': redis_url,
        'result_backend': redis_url,
        'broker_connection_retry_on_startup': True,
        'broker_connection_retry': True,
        'result_backend_transport_options': {
            'socket_connect_timeout': 30,
            'socket_timeout': 30,
            'retry_on_timeout': True
        }
    }
    
    celery = Celery(app.import_name, **celery_config)
    celery.conf.update(app.config)
    
    class ContextTask(celery.Task):
        """Make celery tasks work with Flask app context."""
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery.Task = ContextTask
    return celery

celery = make_celery(app)

# إعداد نظام Logging المتقدم
def setup_logging():
    """إعداد نظام تتبع الأخطاء المتقدم"""
    # إنشاء مجلد logs
    log_dir = os.path.join(os.getcwd(), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # إعداد logger
    logger = logging.getLogger('video_processor')
    logger.setLevel(logging.DEBUG)
    
    # تنسيق الرسائل
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s'
    )
    
    # ملف log للأخطاء
    error_handler = logging.FileHandler(os.path.join(log_dir, 'errors.log'), encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    
    # ملف log عام
    info_handler = logging.FileHandler(os.path.join(log_dir, 'app.log'), encoding='utf-8')
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)
    
    # Console output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(error_handler)
    logger.addHandler(info_handler)
    logger.addHandler(console_handler)
    
    return logger

# إنشاء logger عام
logger = setup_logging()

# دالة لتتبع الأخطاء بتفصيل عجيب
def log_detailed_error(error, context="Unknown", extra_data=None):
    """تسجيل خطأ مفصل مع جميع المعلومات الممكنة"""
    error_id = str(uuid.uuid4())[:8]
    timestamp = datetime.datetime.now().isoformat()
    
    error_details = {
        'error_id': error_id,
        'timestamp': timestamp,
        'context': context,
        'error_type': type(error).__name__,
        'error_message': str(error),
        'traceback': traceback.format_exc(),
        'system_info': {
            'python_version': sys.version,
            'platform': sys.platform,
            'cwd': os.getcwd(),
        },
        'environment': {
            'FLASK_ENV': os.environ.get('FLASK_ENV'),
            'DEBUG': os.environ.get('DEBUG'),
            'REDIS_URL': os.environ.get('REDIS_URL', 'Not set'),
            'UPLOAD_FOLDER': app.config.get('UPLOAD_FOLDER'),
            'OUTPUT_FOLDER': app.config.get('OUTPUT_FOLDER'),
        }
    }
    
    if extra_data:
        error_details['extra_data'] = extra_data
    
    # طباعة مفصلة للخطأ
    logger.error("="*80)
    logger.error(f"🚨 DETAILED ERROR REPORT - ID: {error_id}")
    logger.error("="*80)
    logger.error(f"⏰ Timestamp: {timestamp}")
    logger.error(f"📍 Context: {context}")
    logger.error(f"🔥 Error Type: {type(error).__name__}")
    logger.error(f"💬 Error Message: {str(error)}")
    logger.error("📊 System Info:")
    for key, value in error_details['system_info'].items():
        logger.error(f"   {key}: {value}")
    logger.error("🌍 Environment:")
    for key, value in error_details['environment'].items():
        logger.error(f"   {key}: {value}")
    if extra_data:
        logger.error("📋 Extra Data:")
        for key, value in extra_data.items():
            logger.error(f"   {key}: {value}")
    logger.error("🔍 Full Traceback:")
    logger.error(traceback.format_exc())
    logger.error("="*80)
    
    return error_id, error_details

# إنشاء المجلدات المطلوبة
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# مسارات الملفات الثابتة
ASSETS_FOLDER = 'assets'
WATERMARK_PATH = os.path.join(ASSETS_FOLDER, 'watermark.png')
OUTRO_PATH = os.path.join(ASSETS_FOLDER, 'outro.mp4')

# التحقق من وجود الملفات الثابتة عند بدء التطبيق
if not os.path.exists(WATERMARK_PATH):
    logger.error(f"❌ العلامة المائية غير موجودة: {WATERMARK_PATH}")
if not os.path.exists(OUTRO_PATH):
    logger.error(f"❌ الأوترو غير موجود: {OUTRO_PATH}")

logger.info(f"✅ مسار العلامة المائية: {WATERMARK_PATH}")
logger.info(f"✅ مسار الأوترو: {OUTRO_PATH}")

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
        error_id, _ = log_detailed_error(e, "get_video_info", {"video_path": video_path})
        print(f"❌ خطأ في الحصول على معلومات الفيديو [ID: {error_id}]: {e}")
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
        error_id, _ = log_detailed_error(e, "test_gpu_support")
        print(f"❌ خطأ في اختبار GPU [ID: {error_id}]: {e}")
        return False

def get_optimized_nvenc_settings():
    """إعدادات NVENC محسنة للسرعة والجودة المتوازنة"""
    return [
        '-preset', 'p1',           # أسرع preset
        '-cq', '23',               # جودة متوازنة (23 بدل 25)
        '-b:v', '6M',              # معدل بت متوسط
        '-maxrate', '8M',          # أقصى معدل بت
        '-bufsize', '12M',         # بفر متوسط
        '-gpu', '0',               # استخدام أول GPU
        '-spatial-aq', '1',        # تحسين جودة المناطق
        '-temporal-aq', '1',       # تحسين جودة الحركة
    ]

def process_video_ffmpeg_gpu(video_path, output_path):
    """معالجة الفيديو باستخدام FFmpeg مع تسريع GPU في تمرير واحد"""
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # استخدام h264_nvenc فقط (أسرع وأكثر توافقاً)
            encoder = 'h264_nvenc'
            
            # التحقق من دعم NVENC
            nvenc_available = get_nvenc_encoder()
            if not nvenc_available or 'h264_nvenc' not in nvenc_available:
                print("❌ h264_nvenc غير متوفر، استخدم CPU")
                return False

            # معلومات الفيديوهات
            video_info = get_video_info(video_path)
            outro_info = get_video_info(OUTRO_PATH)
            if not video_info or not outro_info:
                return False

            video_stream = next((s for s in video_info['streams'] if s['codec_type'] == 'video'), None)
            if not video_stream:
                return False

            width = int(video_stream['width'])
            height = int(video_stream['height'])
            video_has_audio = any(s['codec_type'] == 'audio' for s in video_info['streams'])
            outro_has_audio = any(s['codec_type'] == 'audio' for s in outro_info['streams'])

            print(f"🚀 معالجة GPU في تمرير واحد: {width}x{height}")

            # بناء filter_complex للمعالجة الكاملة في تمرير واحد
            if video_has_audio and outro_has_audio:
                filter_complex = (
                    f'[0:v]scale={width}:{height}[v0];'
                    f'[1:v]scale={width}:{height}[v1];'
                    f'[v0][v1]overlay=0:0:enable=\'between(t,0,{float(video_info["format"]["duration"])})\':format=auto,'
                    f'colorchannelmixer=aa=0.3[v0_wm];'
                    f'[v0_wm][0:a][v1][1:a]concat=n=2:v=1:a=1[outv][outa]'
                )
                map_args = ['-map', '[outv]', '-map', '[outa]']
                audio_codec = ['-c:a', 'aac', '-b:a', '128k']
            elif video_has_audio and not outro_has_audio:
                filter_complex = (
                    f'[0:v]scale={width}:{height}[v0];'
                    f'[1:v]scale={width}:{height}[v1];'
                    f'[v0][v1]overlay=0:0:enable=\'between(t,0,{float(video_info["format"]["duration"])})\':format=auto,'
                    f'colorchannelmixer=aa=0.3[v0_wm];'
                    f'[v0_wm][0:a][v1]concat=n=2:v=1:a=1[outv][outa]'
                )
                map_args = ['-map', '[outv]', '-map', '[outa]']
                audio_codec = ['-c:a', 'copy']
            else:
                filter_complex = (
                    f'[0:v]scale={width}:{height}[v0];'
                    f'[1:v]scale={width}:{height}[v1];'
                    f'[v0][v1]overlay=0:0:enable=\'between(t,0,{float(video_info["format"]["duration"])})\':format=auto,'
                    f'colorchannelmixer=aa=0.3[v0_wm];'
                    f'[v0_wm][v1]concat=n=2:v=1[outv]'
                )
                map_args = ['-map', '[outv]']
                audio_codec = ['-an']

            # أمر FFmpeg واحد للمعالجة الكاملة
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', OUTRO_PATH,
                '-filter_complex', filter_complex
            ]
            cmd.extend(map_args)
            cmd.extend(['-c:v', encoder])
            cmd.extend(get_optimized_nvenc_settings())
            cmd.extend(audio_codec)
            cmd.extend(['-movflags', '+faststart'])
            cmd.append(output_path)

            print("🚀 معالجة GPU في تمرير واحد...")
            print(f"أمر FFmpeg: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ تمت المعالجة بنجاح في تمرير واحد!")
                return True
            else:
                print(f"❌ خطأ في المعالجة: {result.stderr}")
                return False

        except Exception as e:
            error_id, _ = log_detailed_error(e, "process_video_ffmpeg_gpu", {
                'video_path': video_path,
                'output_path': output_path,
                'encoder': encoder
            })
            print(f"❌ خطأ في معالجة GPU [ID: {error_id}]: {str(e)}")
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

        # حفظ الناتج بإعدادات فائقة السرعة
        final_timeline.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            threads=16,                    # زيادة عدد threads
            preset='ultrafast',            # أسرع preset
            ffmpeg_params=['-crf', '28'],  # جودة أقل للسرعة
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

        # أمر FFmpeg لدمج الفيديوهات بإعدادات محسنة
        encoder = get_nvenc_encoder()
        if encoder and 'h264_nvenc' in encoder:
            # استخدام GPU للدمج
            merge_cmd = [
                'ffmpeg', '-y',
                '-i', video1_path,
                '-i', video2_path,
                '-filter_complex', '[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[outv][outa]',
                '-map', '[outv]',
                '-map', '[outa]',
                '-c:v', 'h264_nvenc',
                '-c:a', 'aac',
                '-preset', 'p1',
                '-cq', '23',
                '-b:v', '6M',
                merged_path
            ]
        else:
            # استخدام CPU مع أسرع إعدادات
            merge_cmd = [
                'ffmpeg', '-y',
                '-i', video1_path,
                '-i', video2_path,
                '-filter_complex', '[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[outv][outa]',
                '-map', '[outv]',
                '-map', '[outa]',
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-preset', 'ultrafast',
                '-crf', '26',             # جودة محسنة (26 بدل 28)
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
        error_id, error_details = log_detailed_error(e, "process_video_task", {
            'video_path': video_path,
            'output_path': output_path,
            'video2_path': video2_path,
            'task_id': self.request.id
        })
        
        error_message = f"خطأ في المعالجة [ID: {error_id}]: {str(e)}"
        logger.error(f"❌ {error_message}")
        
        self.update_state(
            state='FAILURE', 
            meta={
                'progress': 0, 
                'status': error_message,
                'error_id': error_id,
                'error_details': error_details,
                'timestamp': datetime.datetime.now().isoformat()
            }
        )
        raise

def process_video_direct(video_path, output_path, video2_path=None):
    """معالجة مباشرة بدون Celery (fallback mode)"""
    try:
        logger.info("🔍 بدء المعالجة المباشرة...")
        
        # دمج الفيديوهات إذا كان هناك فيديو ثاني
        final_video_path = video_path
        if video2_path:
            logger.info("🔗 دمج الفيديوهات...")
            merged_path = merge_videos(video_path, video2_path)
            if merged_path:
                final_video_path = merged_path
            else:
                logger.warning("⚠️ فشل دمج الفيديوهات، استخدام الفيديو الأول فقط")

        # فحص GPU
        gpu_supported = test_gpu_support()

        if gpu_supported:
            logger.info("🚀 استخدام GPU (NVENC)...")
            if process_video_ffmpeg_gpu(final_video_path, output_path):
                # تنظيف الملف المدموج المؤقت
                if video2_path and final_video_path != video_path:
                    try:
                        os.unlink(final_video_path)
                    except:
                        pass
                logger.info("✅ تمت المعالجة بنجاح باستخدام GPU!")
                return True
            else:
                logger.warning("⚠️ فشل GPU، الانتقال إلى CPU...")

        logger.info("🖥️ استخدام MoviePy (CPU)...")
        result = process_video_fallback(final_video_path, output_path)
        
        # تنظيف الملف المدموج المؤقت
        if video2_path and final_video_path != video_path:
            try:
                os.unlink(final_video_path)
            except:
                pass
        
        if result:
            logger.info("✅ تمت المعالجة بنجاح باستخدام CPU!")
            return True
        
        return False

    except Exception as e:
        error_id, _ = log_detailed_error(e, "process_video_direct", {
            'video_path': video_path,
            'output_path': output_path,
            'video2_path': video2_path
        })
        logger.error(f"❌ خطأ في المعالجة المباشرة [ID: {error_id}]: {str(e)}")
        return False

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

        # محاولة استخدام Celery، مع fallback للمعالجة المباشرة
        try:
            # فحص اتصال Redis أولاً
            from redis import Redis
            redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
            r = Redis.from_url(redis_url, socket_connect_timeout=2)
            r.ping()
            
            # إذا نجح الاتصال، استخدم Celery
            task = process_video_task.apply_async(args=[video_path, output_path, video2_path])
            
            logger.info(f"✅ استخدام Celery - Task ID: {task.id}")
            
            return jsonify({
                'success': True,
                'job_id': task.id,
                'status': 'queued',
                'message': 'تم بدء معالجة الفيديو باستخدام Celery',
                'output_filename': output_filename,
                'mode': 'async'
            })
            
        except Exception as redis_error:
            # Fallback: معالجة مباشرة بدون Celery
            logger.warning(f"⚠️ فشل Celery، استخدام المعالجة المباشرة: {redis_error}")
            
            # معالجة مباشرة (مع timeout أطول)
            success = process_video_direct(video_path, output_path, video2_path)
            
            if success:
                # تنظيف مجلد المشروع المؤقت
                try:
                    shutil.rmtree(project_folder)
                except Exception:
                    pass
                
                return jsonify({
                    'success': True,
                    'message': 'تمت معالجة الفيديو بنجاح (معالجة مباشرة)',
                    'download_url': f'/download/{output_filename}',
                    'filename': output_filename,
                    'mode': 'direct'
                })
            else:
                return jsonify({'error': 'فشل في معالجة الفيديو'}), 500

    except Exception as e:
        error_id, error_details = log_detailed_error(e, "upload_video", {
            'files_received': list(request.files.keys()),
            'form_data': dict(request.form),
            'content_length': request.content_length,
            'remote_addr': request.remote_addr,
            'user_agent': request.headers.get('User-Agent')
        })
        
        error_message = f"خطأ في الخادم [ID: {error_id}]: {str(e)}"
        logger.error(f"❌ Upload Error: {error_message}")
        
        return jsonify({
            'error': error_message,
            'error_id': error_id,
            'timestamp': datetime.datetime.now().isoformat(),
            'debug_info': error_details if app.config.get('DEBUG') else None
        }), 500

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
        error_id, error_details = log_detailed_error(e, "task_status", {
            'task_id': task_id,
            'remote_addr': request.remote_addr
        })
        
        error_message = f"خطأ في استعلام الحالة [ID: {error_id}]: {str(e)}"
        logger.error(f"❌ Status Error: {error_message}")
        
        return jsonify({
            'error': error_message,
            'error_id': error_id,
            'timestamp': datetime.datetime.now().isoformat()
        }), 500

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

@app.route('/api/test')
def api_test():
    """اختبار بسيط للاتصال"""
    return jsonify({
        'message': 'API يعمل بشكل صحيح',
        'timestamp': str(uuid.uuid4()),
        'status': 'ok'
    })

@app.route('/health')
def health_check():
    """فحص صحة التطبيق والاتصال بـ Redis"""
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    
    try:
        # فحص الاتصال بـ Redis مع معالجة أفضل
        from redis import Redis
        
        # محاولة اتصال مع timeout قصير
        r = Redis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=5)
        r.ping()
        redis_status = "connected"
        
    except Exception as e:
        error_id, _ = log_detailed_error(e, "redis_health_check", {"redis_url": redis_url})
        redis_status = f"disconnected [ID: {error_id}]: {str(e)}"
    
    return jsonify({
        'status': 'healthy',
        'redis': redis_status,
        'celery': 'configured',
        'upload_folder': app.config['UPLOAD_FOLDER'],
        'output_folder': app.config['OUTPUT_FOLDER']
    })

@app.route('/debug/errors')
def get_recent_errors():
    """عرض آخر الأخطاء المسجلة (للمطورين فقط)"""
    try:
        log_file = os.path.join('logs', 'errors.log')
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # آخر 50 سطر
                recent_errors = lines[-50:] if len(lines) > 50 else lines
                
            return jsonify({
                'total_lines': len(lines),
                'recent_errors': recent_errors,
                'log_file': log_file,
                'timestamp': datetime.datetime.now().isoformat()
            })
        else:
            return jsonify({'message': 'لا توجد أخطاء مسجلة', 'log_file': log_file})
            
    except Exception as e:
        error_id, _ = log_detailed_error(e, "get_recent_errors")
        return jsonify({'error': f'خطأ في قراءة سجل الأخطاء [ID: {error_id}]: {str(e)}'}), 500

@app.route('/debug/system')
def system_info():
    """معلومات النظام التفصيلية"""
    # معلومات النظام الأساسية بدون psutil
    system_data = {
        'disk_usage': get_disk_usage(),
        'memory_info': get_memory_info(),
        'process_info': {
            'pid': os.getpid(),
            'cwd': os.getcwd(),
            'uid': os.getuid() if hasattr(os, 'getuid') else 'N/A',
        }
    }
    
    return jsonify({
        'python_version': sys.version,
        'platform': sys.platform,
        'cwd': os.getcwd(),
        'environment_variables': {
            key: value for key, value in os.environ.items() 
            if not key.startswith('SECRET')  # إخفاء المفاتيح السرية
        },
        'flask_config': {
            'UPLOAD_FOLDER': app.config.get('UPLOAD_FOLDER'),
            'OUTPUT_FOLDER': app.config.get('OUTPUT_FOLDER'),
            'MAX_CONTENT_LENGTH': app.config.get('MAX_CONTENT_LENGTH'),
        },
        'system': system_data,
        'timestamp': datetime.datetime.now().isoformat()
    })

def get_disk_usage():
    """الحصول على معلومات استخدام القرص"""
    try:
        if hasattr(shutil, 'disk_usage'):
            total, used, free = shutil.disk_usage('/')
            return {
                'total': total,
                'used': used,
                'free': free,
                'percent': round((used / total) * 100, 2)
            }
    except:
        pass
    return {'note': 'disk usage info not available'}

def get_memory_info():
    """الحصول على معلومات الذاكرة بدون psutil"""
    try:
        # قراءة من /proc/meminfo في Linux
        if os.path.exists('/proc/meminfo'):
            with open('/proc/meminfo', 'r') as f:
                meminfo = {}
                for line in f:
                    parts = line.split(':')
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        if 'kB' in value:
                            value = int(value.replace('kB', '').strip()) * 1024
                        meminfo[key] = value
                
                total = meminfo.get('MemTotal', 0)
                available = meminfo.get('MemAvailable', 0)
                return {
                    'total': total,
                    'available': available,
                    'used': total - available,
                    'percent': round(((total - available) / total) * 100, 2) if total > 0 else 0
                }
    except:
        pass
    return {'note': 'memory info not available'}

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
