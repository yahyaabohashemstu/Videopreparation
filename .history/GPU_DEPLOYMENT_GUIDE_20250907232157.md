# 🚀 دليل النشر مع دعم GPU/NVENC

## 📋 المتطلبات الأساسية

### 1️⃣ **على الخادم (Host)**

```bash
# تثبيت nvidia-container-toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# إعادة تشغيل Docker
sudo systemctl restart docker
```

### 2️⃣ **التحقق من دعم GPU**

```bash
# اختبار Docker GPU
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi

# اختبار FFmpeg NVENC
docker run --rm --gpus all jrottenberg/ffmpeg:6.1-nvidia ffmpeg -encoders | grep nvenc
```

## 🔧 **النشر على Coolify**

### **الطريقة 1: استخدام Dockerfile.nvidia (موصى به)**

1. **في Coolify - API Service:**

   - Repository: `yahyaabohashemstu/Videopreparation`
   - Branch: `main`
   - Dockerfile: `Dockerfile.nvidia`
   - Environment Variables: استخدم `production.env`
   - **Enable GPU**: ✅ فعّل

2. **في Coolify - Worker Service:**
   - Repository: `yahyaabohashemstu/Videopreparation`
   - Branch: `main`
   - Dockerfile: `Dockerfile.nvidia`
   - Environment Variables: استخدم `worker.env`
   - **Enable GPU**: ✅ فعّل
   - **Command Override**: `celery -A app.celery worker --loglevel=info --concurrency=2`

### **الطريقة 2: استخدام docker-compose.nvidia.yml محلياً**

```bash
# تشغيل مع دعم GPU
docker-compose -f docker-compose.nvidia.yml up -d

# مراقبة الـ logs
docker-compose -f docker-compose.nvidia.yml logs -f video-processor-worker
```

## ⚡ **إعدادات الأداء المحسنة**

### **للخوادم القوية (8+ أنوية + GPU)**

```env
# في worker.env
CELERY_CONCURRENCY=4
FFMPEG_THREADS=12
NVENC_CQ=18
NVENC_MAXRATE=20M
NVENC_BUFSIZE=40M
```

### **للخوادم المتوسطة (4 أنوية + GPU)**

```env
# في worker.env
CELERY_CONCURRENCY=2
FFMPEG_THREADS=6
NVENC_CQ=19
NVENC_MAXRATE=16M
NVENC_BUFSIZE=32M
```

### **للخوادم الضعيفة (بدون GPU)**

```env
# في worker.env
GPU_ACCELERATION=false
X264_PRESET=ultrafast
X264_CRF=22
FFMPEG_THREADS=4
```

## 🔍 **التحقق من عمل GPU**

### **1. فحص الـ logs**

```bash
# البحث عن رسائل NVENC
docker logs video-processor-worker | grep "NVENC"

# البحث عن رسائل GPU
docker logs video-processor-worker | grep "GPU"
```

### **2. اختبار API**

```bash
# اختبار GPU support
curl https://your-domain.com/test-gpu

# يجب أن ترى:
# {"gpu_available": true, "nvenc_encoder": "h264_nvenc"}
```

### **3. مراقبة الأداء**

```bash
# مراقبة استخدام GPU
nvidia-smi

# مراقبة استخدام CPU
htop
```

## 🚨 **استكشاف الأخطاء**

### **مشكلة: NVENC غير متاح**

```bash
# الحل: تأكد من تثبيت nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### **مشكلة: FFmpeg لا يجد NVENC**

```bash
# الحل: استخدم Dockerfile.nvidia بدلاً من Dockerfile العادي
# أو تأكد من استخدام jrottenberg/ffmpeg:nvidia كـ base image
```

### **مشكلة: بطيء رغم GPU**

```bash
# الحل: اضبط NVENC_CQ (أقل = أسرع، أعلى = جودة أفضل)
# NVENC_CQ=15 (أسرع) vs NVENC_CQ=23 (جودة أعلى)
```

## 📊 **مقارنة الأداء المتوقع**

| الإعداد             | السرعة | الجودة     | الاستهلاك  |
| ------------------- | ------ | ---------- | ---------- |
| **NVENC p1 + CQ19** | ⚡⚡⚡ | ⭐⭐⭐⭐   | 🔋🔋🔋     |
| **NVENC p1 + CQ23** | ⚡⚡   | ⭐⭐⭐⭐⭐ | 🔋🔋       |
| **x264 veryfast**   | ⚡⚡   | ⭐⭐⭐     | 🔋🔋🔋🔋   |
| **x264 ultrafast**  | ⚡⚡⚡ | ⭐⭐       | 🔋🔋🔋🔋🔋 |

## 🎯 **النتائج المتوقعة**

- **مع GPU**: معالجة فيديو 10 دقائق في 30-60 ثانية
- **بدون GPU**: معالجة فيديو 10 دقائق في 2-5 دقائق
- **جودة عالية**: CQ 19-23 مع NVENC
- **استقرار**: عدم ضياع المهام مع Celery reliability settings

---

## ✅ **التحقق النهائي**

1. ✅ nvidia-container-toolkit مثبت
2. ✅ Dockerfile.nvidia يستخدم jrottenberg/ffmpeg:nvidia
3. ✅ Coolify مفعل GPU للـ Worker
4. ✅ متغيرات البيئة صحيحة
5. ✅ API يعيد `{"gpu_available": true}`

**🎉 المشروع جاهز للنشر مع دعم GPU كامل!**
