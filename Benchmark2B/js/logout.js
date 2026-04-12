(function () {
  var logoutTargets = document.querySelectorAll("#logoutBtn, .logout, .Logout");

  if (!logoutTargets.length) return;

  function logout(event) {
    if (event) {
      event.preventDefault();
    }

    try {
      sessionStorage.removeItem("userRole");
      sessionStorage.removeItem("userEmail");
      localStorage.removeItem("userRole");
      localStorage.removeItem("userEmail");
      localStorage.removeItem("authToken");
    } catch (error) {
      // Ignore storage access issues and continue to the login page.
    }

    window.location.href = "./index.html";
  }

  logoutTargets.forEach(function (target) {
    if (target.tagName === "A") {
      target.setAttribute("href", "index.html");
    }

    target.addEventListener("click", logout);
  });
})();
