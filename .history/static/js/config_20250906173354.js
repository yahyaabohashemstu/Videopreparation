// Frontend Configuration
// يتم تحديد API_BASE تلقائياً حسب البيئة
(function () {
  // تحديد البيئة الحالية
  const hostname = window.location.hostname;
  const protocol = window.location.protocol;
  const port = window.location.port;

  if (hostname === "localhost" || hostname === "127.0.0.1") {
    // Development environment
    window.API_BASE = `${protocol}//${hostname}:5000`;
  } else {
    // Production environment - استخدام نفس الدومين والبورت
    // في Coolify، عادة ما يكون التطبيق على نفس الدومين
    if (port && port !== '80' && port !== '443') {
      window.API_BASE = `${protocol}//${hostname}:${port}`;
    } else {
      window.API_BASE = `${protocol}//${hostname}`;
    }
  }

  console.log("API Base URL:", window.API_BASE);
  console.log("Current location:", window.location.href);
})();
