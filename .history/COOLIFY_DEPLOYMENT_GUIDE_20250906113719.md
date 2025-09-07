# 🚀 دليل نشر مشروع معالج الفيديو على Coolify

## 📋 متطلبات ما قبل النشر

### 1. **تجهيز المشروع**

- تأكد من وجود جميع الملفات المطلوبة
- تحديث ملف `requirements.txt`
- مراجعة إعدادات `Dockerfile` و `docker-compose.yml`

### 2. **إعداد Git Repository**

```bash
# إذا لم تكن قد أنشأت مستودع git بعد
git init
git add .
git commit -m "Initial commit - Video Processor App"

# رفع المشروع إلى GitHub/GitLab
git remote add origin https://github.com/your-username/video-processor.git
git push -u origin main
```

## 🔧 خطوات النشر على Coolify

### **الخطوة 1: إعداد المشروع في Coolify**

1. **تسجيل الدخول إلى Coolify**

   - اذهب إلى لوحة تحكم Coolify الخاصة بك
   - سجل دخولك إلى الحساب

2. **إنشاء مشروع جديد**

   - اضغط على "New Resource" أو "إضافة مورد جديد"
   - اختر "Application" من القائمة

3. **ربط المستودع**
   - اختر "Git Repository"
   - أدخل رابط المستودع: `https://github.com/your-username/video-processor.git`
   - اختر الفرع: `main` أو `master`

### **الخطوة 2: إعداد التطبيق**

1. **معلومات أساسية**

   - **Name**: `video-processor`
   - **Description**: `معالج الفيديو - إضافة العلامة المائية والأوترو`

2. **إعدادات البناء**

   - **Build Pack**: Docker
   - **Dockerfile Path**: `./Dockerfile`
   - **Docker Compose Path**: `./docker-compose.yml` (اختياري)

3. **إعدادات البورت**
   - **Port**: `5000`
   - **Protocol**: HTTP

### **الخطوة 3: إعداد متغيرات البيئة**

في قسم "Environment Variables" أضف المتغيرات التالية:

```env
# متغيرات أساسية
SECRET_KEY=your-super-secure-secret-key-here
PORT=5000
DEBUG=false
FLASK_ENV=production

# إعدادات الملفات
UPLOAD_FOLDER=uploads
OUTPUT_FOLDER=outputs
MAX_CONTENT_LENGTH=524288000

# إعدادات الأداء
GUNICORN_WORKERS=2
GUNICORN_TIMEOUT=300
```

### **الخطوة 4: إعدادات الذاكرة والموارد**

1. **Memory Limit**: `2GB` (موصى به للمعالجة)
2. **CPU Limit**: `1 CPU` (أو حسب الحاجة)
3. **Storage**: `5GB` (للملفات المؤقتة)

### **الخطوة 5: إعدادات الشبكة والدومين**

1. **Domain Setup**:

   - أضف الدومين المخصص (مثل: `video.yourdomain.com`)
   - أو استخدم الدومين الافتراضي من Coolify

2. **SSL Certificate**:
   - فعل "Auto SSL" للحصول على شهادة مجانية
   - أو ارفع شهادتك الخاصة

### **الخطوة 6: إعداد التخزين المستمر**

1. **Persistent Volumes**:

   ```yaml
   # في قسم Storage/Volumes
   - /app/uploads:/data/uploads
   - /app/outputs:/data/outputs
   ```

2. **Backup Configuration**:
   - فعل النسخ الاحتياطي التلقائي للمجلدات المهمة

## ⚙️ إعدادات متقدمة

### **1. Health Checks**

```yaml
# Coolify سيستخدم هذه الإعدادات تلقائياً من Dockerfile
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### **2. إعدادات Reverse Proxy**

```nginx
# إعدادات إضافية للـ Nginx (إذا لزم الأمر)
client_max_body_size 500M;
proxy_read_timeout 300s;
proxy_connect_timeout 60s;
proxy_send_timeout 300s;
```

### **3. إعدادات الأمان**

```env
# متغيرات أمان إضافية
FLASK_CORS_ORIGINS=https://yourdomain.com
SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
```

## 🚀 عملية النشر

### **البناء والنشر**

1. اضغط على "Deploy" في Coolify
2. راقب سجلات البناء (Build Logs)
3. تأكد من عدم وجود أخطاء في البناء
4. انتظر حتى يصبح التطبيق "Running"

### **اختبار التطبيق**

1. اذهب إلى الرابط المخصص للتطبيق
2. تأكد من تحميل الواجهة بشكل صحيح
3. جرب رفع ملف فيديو صغير للاختبار
4. تحقق من عمل endpoint الصحة: `/health`

## 🔍 استكشاف الأخطاء

### **مشاكل شائعة وحلولها**

1. **خطأ في بناء Docker**:

   ```bash
   # تحقق من ملف Dockerfile
   # تأكد من وجود جميع التبعيات في requirements.txt
   ```

2. **مشكلة في الذاكرة**:

   - زيادة حد الذاكرة إلى 2GB أو أكثر
   - تقليل عدد workers في gunicorn

3. **مشكلة في رفع الملفات الكبيرة**:

   ```env
   MAX_CONTENT_LENGTH=524288000  # 500MB
   ```

4. **مشكلة FFmpeg**:
   - التطبيق سيتحول تلقائياً إلى معالجة CPU إذا لم يتوفر GPU
   - تحقق من سجلات التطبيق

### **مراقبة الأداء**

1. **Logs**: راقب سجلات التطبيق في Coolify
2. **Metrics**: تابع استهلاك الذاكرة والمعالج
3. **Health Checks**: تأكد من استجابة `/health` endpoint

## 📝 نصائح مهمة

### **الأمان**

- غير `SECRET_KEY` إلى قيمة قوية وفريدة
- استخدم HTTPS دائماً في الإنتاج
- فعل CORS للدومينات المطلوبة فقط

### **الأداء**

- استخدم CDN للملفات الثابتة إذا أمكن
- فعل ضغط gzip في Nginx
- راقب استهلاك التخزين وامسح الملفات القديمة

### **الصيانة**

- أنشئ نسخة احتياطية دورية للبيانات
- راقب سجلات الأخطاء بانتظام
- حدث التبعيات بشكل دوري

## 🔄 تحديث التطبيق

لتحديث التطبيق:

1. ادفع التغييرات إلى Git repository
2. اذهب إلى Coolify واضغط "Redeploy"
3. راقب عملية البناء الجديدة
4. اختبر التطبيق بعد التحديث

---

## 📞 الدعم والمساعدة

إذا واجهت أي مشاكل:

1. تحقق من سجلات Coolify
2. راجع سجلات التطبيق
3. تأكد من إعدادات متغيرات البيئة
4. تحقق من إعدادات الذاكرة والموارد

**تم إنشاء هذا الدليل بواسطة Claude AI** 🤖
