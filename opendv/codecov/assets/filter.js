<script>
(function(){var q=document.getElementById('q'),ty=document.getElementById('ty'),rows=document.querySelectorAll('tr[data-t]'),n=document.getElementById('n');
function f(){var s=q.value.toLowerCase(),t=ty.value,c=0;rows.forEach(function(r){var ok=(!s||r.dataset.t.indexOf(s)>=0)&&(!t||r.dataset.ty===t);r.style.display=ok?'':'none';c+=ok;});n.textContent=c;}
q.addEventListener('input',f);ty.addEventListener('change',f);})();</script>