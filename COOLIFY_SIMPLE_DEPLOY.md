# 🚀 دليل النشر المبسط على Coolify

## 🎯 **النشر السريع (تطبيق واحد فقط)**

### **الخطوة 1: إنشاء التطبيق**
1. **New Application** → **Git Repository**
2. **Repository**: `https://github.com/yahyaabohashemstu/Videopreparation.git`
3. **Branch**: `main`
4. **Build Pack**: Docker (سيتم اكتشافه تلقائياً)

### **الخطوة 2: الإعدادات الأساسية**
- **Name**: `video-processor`
- **Port**: `5000`
- **Memory**: `3GB` (مهم للمعالجة)
- **CPU**: `2 cores`

### **الخطوة 3: متغيرات البيئة**
```env
SECRET_KEY=your-super-secure-secret-key-change-this
UPLOAD_FOLDER=/data/uploads
OUTPUT_FOLDER=/data/outputs
MAX_CONTENT_LENGTH=524288000
FLASK_ENV=production
DEBUG=false
GUNICORN_WORKERS=3
GUNICORN_THREADS=8
```

### **الخطوة 4: النشر**
- **اضغط "Deploy"**
- **راقب Build Logs**
- **انتظر حتى "Running"**

---

## ⚡ **النشر المتقدم (مع Redis و Celery)**

### **الخطوة 1: إضافة Redis**
1. **Marketplace** → **Redis**
2. **Name**: `redis`
3. **Version**: `7-alpine`
4. **Deploy**

### **الخطوة 2: Flask API**
```env
# نفس الإعدادات السابقة + 
REDIS_URL=redis://redis:6379/0
```

### **الخطوة 3: Celery Worker**
1. **New Application** → **Git Repository**
2. **Repository**: نفس المستودع
3. **Name**: `video-processor-worker`
4. **Environment Variables**:
```env
WORKER_MODE=celery
REDIS_URL=redis://redis:6379/0
CELERY_CONCURRENCY=3
SECRET_KEY=same-as-api
UPLOAD_FOLDER=/data/uploads
OUTPUT_FOLDER=/data/outputs
```
5. **Memory**: `4GB`
6. **No Port** (worker لا يحتاج port)

---

## 🔧 **الميزات الجديدة:**

### **🎛️ نمط مرن:**
- **بدون Redis**: معالجة مباشرة (أبطأ لكن موثوق)
- **مع Redis**: معالجة غير متزامنة (أسرع ولا timeout)

### **⚙️ إعدادات ديناميكية:**
- `WORKER_MODE=celery` → Celery Worker
- `WORKER_MODE=` (فارغ) → Flask API
- `GUNICORN_WORKERS` → عدد العمليات
- `CELERY_CONCURRENCY` → عدد المعالجات المتوازية

### **🛡️ أمان محسن:**
- **صلاحيات صحيحة** لجميع المجلدات
- **Non-root user** مع ownership صحيح
- **Error handling** مع `|| true`

---

## 📋 **إعدادات موصى بها:**

### **للاستخدام البسيط:**
```
Memory: 3GB
CPU: 2 cores
Storage: 10GB
```

### **للاستخدام المكثف:**
```
API: 2GB memory
Worker: 4GB memory  
Redis: 512MB memory
Storage: 20GB
```

---

## 🎯 **نصائح النشر:**

1. **ابدأ بالنشر البسيط** (تطبيق واحد)
2. **اختبر المعالجة** مع فيديو صغير
3. **إذا كان بطيء، أضف Redis و Worker**
4. **راقب الأداء** في Coolify metrics

**🎊 هذا Dockerfile سيعمل في جميع الحالات! جاهز للنشر! 🚀**
