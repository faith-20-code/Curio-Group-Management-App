document.addEventListener("DOMContentLoaded", () => {
  const menuItems = document.querySelectorAll(".menu-item");
  const pages = document.querySelectorAll(".page");

  menuItems.forEach(item => {
    item.addEventListener("click", (e) => {
      e.preventDefault();

      // active menu
      menuItems.forEach(i => i.classList.remove("active"));
      item.classList.add("active");

      // switch pages
      pages.forEach(page => page.classList.remove("active"));

      const target = item.dataset.target;
      document.getElementById(target).classList.add("active");
    });
  });
});