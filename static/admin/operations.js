/* Operações leves: sem dependências externas, sem expor dados para serviços terceiros. */
(() => {
  const filters = document.querySelector('#orderFilters');
  if (filters) {
    const period = filters.querySelector('[data-period]');
    const range = filters.querySelector('[data-date-range]');
    if (period && range) period.addEventListener('change', () => { range.hidden = period.value !== 'custom'; });
    const query = filters.querySelector('[data-debounce-search]');
    if (query) {
      let timeout;
      query.addEventListener('input', () => {
        window.clearTimeout(timeout);
        timeout = window.setTimeout(() => { if (query.value.length === 0 || query.value.trim().length >= 2) filters.requestSubmit(); }, 500);
      });
    }
  }
  document.querySelectorAll('[data-print]').forEach(button => {
    button.addEventListener('click', () => window.print());
  });
  document.querySelectorAll('[data-confirm]').forEach(form => {
    form.addEventListener('submit', event => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });
  document.querySelectorAll('[data-copy]').forEach(button => {
    button.addEventListener('click', async () => {
      if (!navigator.clipboard || !window.isSecureContext) {
        button.textContent = 'Selecione para copiar'; return;
      }
      try { await navigator.clipboard.writeText(button.dataset.copy || ''); button.textContent = 'Copiado ✓'; }
      catch (_error) { button.textContent = 'Não foi possível copiar'; }
    });
  });
})();
