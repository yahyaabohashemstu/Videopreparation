// Frontend Configuration
// تحديد API_BASE بناءً على البيئة الحالية
(function () {
  // استخدام window.location.origin مباشرة (الأبسط والأكثر موثوقية)
  window.API_BASE = window.location.origin;
  
  console.log("API Base URL:", window.API_BASE);
  console.log("Current location:", window.location.href);
  
  // تحقق إضافي للتطوير المحلي
  if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
    // في التطوير المحلي، قد نحتاج port مختلف
    if (!window.location.port || window.location.port !== "5000") {
      window.API_BASE = `${window.location.protocol}//${window.location.hostname}:5000`;
      console.log("Development override - API Base:", window.API_BASE);
    }
  }
})();
