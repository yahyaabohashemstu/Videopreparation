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
    // Production environment - استخدام نفس الدومين
    window.API_BASE = `${protocol}//${hostname}${port ? ":" + port : ""}`;
  }

  console.log("API Base URL:", window.API_BASE);
})();
