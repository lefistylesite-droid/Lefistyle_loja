(() => {
  const toggle = document.querySelector('[data-menu-toggle]');
  const menu = document.querySelector('#nav-links');
  if (toggle && menu) {
    toggle.addEventListener('click', () => {
      const open = menu.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', String(open));
      toggle.setAttribute('aria-label', open ? 'Fechar menu de categorias' : 'Abrir menu de categorias');
    });
  }
  const thumbnails = document.querySelectorAll('[data-thumb]');
  thumbnails.forEach((button, index) => {
    if (index === 0) button.setAttribute('aria-pressed','true');
    button.addEventListener('click', () => {
      const main = document.querySelector('#mainProductPhoto');
      if (main) {
        main.src = button.dataset.thumb;
        const selectedAlt = button.querySelector('img')?.alt;
        if (selectedAlt) main.alt = selectedAlt;
      }
      thumbnails.forEach(t => t.setAttribute('aria-pressed','false'));
      button.setAttribute('aria-pressed','true');
    });
  });
  const form = document.querySelector('#lefiCheckoutForm');
  const payButton = document.querySelector('#startPaymentButton');
  if (form && payButton) {
    form.addEventListener('submit', () => {
      if (!form.checkValidity()) return;
      payButton.disabled = true;
      payButton.textContent = 'CRIANDO SEU PEDIDO…';
    });
  }
})();
