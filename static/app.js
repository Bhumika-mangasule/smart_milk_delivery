document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("menuToggle"), nav = document.getElementById("mainNav");
  if (toggle && nav) toggle.addEventListener("click", () => nav.classList.toggle("open"));
  const customer = document.getElementById("customerSelect"), price = document.getElementById("priceInput");
  if (customer && price) customer.addEventListener("change", () => {
    const option = customer.options[customer.selectedIndex];
    if (option && option.dataset.price) price.value = option.dataset.price;
  });
  const start = document.getElementById("startDate"), end = document.getElementById("endDate");
  const iso = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
  const week = document.getElementById("weekButton"), month = document.getElementById("monthButton");
  if (week && start && end) week.addEventListener("click", () => { const t=new Date(), s=new Date(t); s.setDate(t.getDate()-6); start.value=iso(s); end.value=iso(t); });
  if (month && start && end) month.addEventListener("click", () => { const t=new Date(); start.value=iso(new Date(t.getFullYear(),t.getMonth(),1)); end.value=iso(t); });
});
