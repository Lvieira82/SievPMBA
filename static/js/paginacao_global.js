(function(){
  function iniciar(container){
    const tamanho=Math.max(1,parseInt(container.dataset.paginaTamanho||10,10));
    const itens=Array.from(container.querySelectorAll('[data-paginavel-item="1"]'));
    if(itens.length<=tamanho)return;
    let pagina=1;
    const total=Math.ceil(itens.length/tamanho);
    const controles=document.createElement('div');
    controles.className='paginacao-global';
    controles.setAttribute('aria-label','Paginação');
    const info=document.createElement('span');info.className='paginacao-info';
    const anterior=document.createElement('button');anterior.type='button';anterior.className='paginacao-btn';anterior.textContent='‹ Anterior';
    const proxima=document.createElement('button');proxima.type='button';proxima.className='paginacao-btn';proxima.textContent='Próxima ›';
    const paginas=document.createElement('span');paginas.className='paginacao-numeros';
    controles.append(anterior,paginas,proxima,info);container.appendChild(controles);
    function render(){
      const inicio=(pagina-1)*tamanho,fim=inicio+tamanho;
      itens.forEach((el,i)=>{el.style.display=(i>=inicio&&i<fim)?'':'none'});
      paginas.innerHTML='';
      const inicioNumeros=Math.max(1,pagina-2),fimNumeros=Math.min(total,inicioNumeros+4);
      for(let n=inicioNumeros;n<=fimNumeros;n++){const b=document.createElement('button');b.type='button';b.className='paginacao-btn'+(n===pagina?' ativo':'');b.textContent=n;b.onclick=()=>{pagina=n;render()};paginas.appendChild(b)}
      anterior.disabled=pagina===1;proxima.disabled=pagina===total;
      info.textContent=`Mostrando ${inicio+1}–${Math.min(fim,itens.length)} de ${itens.length}`;
    }
    anterior.onclick=()=>{if(pagina>1){pagina--;render()}};
    proxima.onclick=()=>{if(pagina<total){pagina++;render()}};
    render();
  }
  function inicializar(){document.querySelectorAll('.paginacao-global-container').forEach(iniciar)}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',inicializar);else inicializar();
})();
