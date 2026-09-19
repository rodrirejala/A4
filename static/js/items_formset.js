(function () {
  var config = window.FORMSET_CONFIG;
  var tbody = document.getElementById('tbody-items');
  var template = document.getElementById('fila-template');
  var btnAgregar = document.getElementById('btn-agregar-fila');
  var totalInput = document.getElementById('id_' + config.prefix + '-TOTAL_FORMS');
  var contador = document.getElementById('contador-items');

  function countRows() {
    return tbody.querySelectorAll('.item-row').length;
  }

  function actualizarContador() {
    if (contador) {
      contador.textContent = countRows() + ' / ' + config.maxForm + ' ítems';
    }
  }

  function renumber() {
    var rows = tbody.querySelectorAll('.item-row');
    rows.forEach(function (row, i) {
      row.querySelectorAll('[name]').forEach(function (el) {
        var parts = el.name.split('-');
        if (parts[0] === config.prefix) {
          parts[1] = String(i);
          el.name = parts.join('-');
        }
      });
      row.querySelectorAll('label[for]').forEach(function (lbl) {
        var parts = lbl.getAttribute('for').split('-');
        if (parts[0] === config.prefix) {
          parts[1] = String(i);
          lbl.setAttribute('for', parts.join('-'));
        }
      });
    });
    if (totalInput) totalInput.value = String(rows.length);
    actualizarContador();
  }

  function esFilaNueva(row) {
    var idRe = new RegExp('^' + config.prefix + '-\\d+-id$');
    var idInput = null;
    row.querySelectorAll('input[name]').forEach(function (el) {
      if (idRe.test(el.name)) idInput = el;
    });
    return !idInput || idInput.value === '';
  }

  function agregarFila() {
    var filas = countRows();
    if (filas >= config.maxForm) {
      alert('No se pueden agregar más de ' + config.maxForm + ' filas (límite del formato).');
      return;
    }
    var clon = template.cloneNode(true);
    clon.id = '';
    clon.classList.remove('d-none');
    var ultima = tbody.querySelector('.item-row:last-of-type');
    if (ultima) {
      ultima.after(clon);
    } else {
      tbody.appendChild(clon);
    }
    renumber();
    var primero = clon.querySelector('input');
    if (primero) primero.focus();
  }

  function quitarFila(btn) {
    var row = btn.closest('.item-row');
    if (esFilaNueva(row)) {
      row.remove();
      renumber();
    } else {
      row.classList.add('fila-eliminada');
      var del = row.querySelector('input[type="checkbox"][name$="-DELETE"]');
      if (del) del.checked = true;
      actualizarContador();
    }
  }

  btnAgregar.addEventListener('click', agregarFila);
  tbody.addEventListener('click', function (e) {
    if (e.target.closest('.quitar-fila')) quitarFila(e.target.closest('.quitar-fila'));
  });

  actualizarContador();
})();