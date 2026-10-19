// Shared by the journal (index.html) and read-only share pages (share.html).

// ── Icons (SF Symbols-style line icons) ──────────────────────────────────────
const ICONS={
  list:'<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="3.5" cy="6" r=".6"/><circle cx="3.5" cy="12" r=".6"/><circle cx="3.5" cy="18" r=".6"/>',
  map:'<path d="M9 4 3 6.5v13L9 17l6 2.5 6-2.5V4l-6 2.5L9 4z"/><path d="M9 4v13M15 6.5v13"/>',
  plus:'<path d="M12 5v14M5 12h14"/>',
  search:'<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.2-4.2"/>',
  pin:'<path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.3"/>',
  tag:'<path d="M3.5 12.2V4.5a1 1 0 0 1 1-1h7.7l8.3 8.3a1.4 1.4 0 0 1 0 2l-6.2 6.2a1.4 1.4 0 0 1-2 0z"/><circle cx="8" cy="8" r="1.3"/>',
  route:'<circle cx="6" cy="18" r="2.2"/><circle cx="18" cy="6" r="2.2"/><path d="M8.2 18H15a3 3 0 0 0 0-6H9a3 3 0 0 1 0-6h6.8"/>',
  pencil:'<path d="M4 20h4L19 9l-4-4L4 16v4z"/><path d="m13.5 6.5 4 4"/>',
  trash:'<path d="M4 7h16M9.5 7V4.5h5V7M6 7l1 13h10l1-13"/>',
  photo:'<rect x="3" y="5" width="18" height="14" rx="2.5"/><circle cx="9" cy="10" r="1.6"/><path d="m21 16-5-5-9 8"/>',
  play:'<path d="M8 5.5v13l10.5-6.5z" fill="currentColor" stroke="none"/>',
  chevL:'<path d="m14.5 5.5-6.5 6.5 6.5 6.5"/>',
  chevR:'<path d="m9.5 5.5 6.5 6.5-6.5 6.5"/>',
  xmark:'<path d="M6 6l12 12M18 6 6 18"/>',
  book:'<rect x="5" y="3" width="14" height="18" rx="2.6"/><path d="M9 3.4v17.2M12.3 7.9h3.2M12.3 11.1h1.8"/>',
  share:'<path d="M12 3.5v11M8 7.5l4-4 4 4"/><path d="M7 11H6a1.5 1.5 0 0 0-1.5 1.5v6A1.5 1.5 0 0 0 6 20h12a1.5 1.5 0 0 0 1.5-1.5v-6A1.5 1.5 0 0 0 18 11h-1"/>',
  mic:'<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/>',
  lock:'<rect x="5" y="10.5" width="14" height="10" rx="2.2"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/>',
  sparkle:'<path d="M12 3.5c.5 4.3 2.2 6 6.5 6.5-4.3.5-6 2.2-6.5 6.5-.5-4.3-2.2-6-6.5-6.5 4.3-.5 6-2.2 6.5-6.5zM18.5 15.5c.2 1.6.8 2.3 2.5 2.5-1.7.2-2.3.9-2.5 2.5-.2-1.6-.8-2.3-2.5-2.5 1.7-.2 2.3-.9 2.5-2.5z"/>',
  clock:'<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  mountain:'<path d="m3 19 6.5-11 4 6.5 2.5-3.5L21 19z"/>',
  calendar:'<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 9.5h17M8 3v4M16 3v4"/>',
  copy:'<rect x="8" y="8" width="12" height="12" rx="2.2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
  // weather
  sun:'<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M4.6 4.6 6 6M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4"/>',
  cloudSun:'<path d="M8 6.5a3.5 3.5 0 0 1 6.4-.9M9.5 2.5v1M4.3 4.3l.8.8M2.5 9.5h1"/><path d="M8 20h9a4 4 0 0 0 0-8 5.5 5.5 0 0 0-10.4 2A3 3 0 0 0 8 20z"/>',
  cloud:'<path d="M7.5 19h10a4.5 4.5 0 0 0 .3-9A6 6 0 0 0 6.2 11.6 3.8 3.8 0 0 0 7.5 19z"/>',
  fog:'<path d="M4 9h16M4 13h16M6 17h12"/>',
  rain:'<path d="M7.5 15h10a4.5 4.5 0 0 0 .3-9A6 6 0 0 0 6.2 7.6 3.8 3.8 0 0 0 7.5 15zM8.5 18l-1 2.5M12.5 18l-1 2.5M16.5 18l-1 2.5"/>',
  snow:'<path d="M7.5 14h10a4.5 4.5 0 0 0 .3-9A6 6 0 0 0 6.2 6.6 3.8 3.8 0 0 0 7.5 14z"/><circle cx="8" cy="18.5" r=".7"/><circle cx="12" cy="20" r=".7"/><circle cx="16" cy="18.5" r=".7"/>',
  storm:'<path d="M7.5 14h10a4.5 4.5 0 0 0 .3-9A6 6 0 0 0 6.2 6.6 3.8 3.8 0 0 0 7.5 14z"/><path d="m12.5 14-2 3.5h3l-2 3.5"/>',
};
function ico(n){return `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true">${ICONS[n]||''}</svg>`;}

// ── Formatting ───────────────────────────────────────────────────────────────
function esc(s){return(s==null?'':String(s)).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');}
function fmtDate(d){if(!d)return'—';return new Date(d+'T00:00:00').toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'});}
function fmtLongDate(d){if(!d)return'';return new Date(d+'T00:00:00').toLocaleDateString('en-GB',{weekday:'long',day:'numeric',month:'long',year:'numeric'});}
function fmtMonth(ym){if(!ym||ym==='—')return'—';const[y,m]=ym.split('-');return new Date(y,m-1,1).toLocaleDateString('en-GB',{month:'long',year:'numeric'});}
function fmtNum(n,dp=0){return Number(n).toLocaleString('en-GB',{maximumFractionDigits:dp});}

// ── Weather (WMO codes from Open-Meteo) ──────────────────────────────────────
function weatherInfo(code){
  if(code===0) return ['sun','Clear'];
  if(code<=2)  return ['cloudSun','Partly cloudy'];
  if(code===3) return ['cloud','Overcast'];
  if(code<=48) return ['fog','Fog'];
  if(code<=57) return ['rain','Drizzle'];
  if(code<=67) return ['rain','Rain'];
  if(code<=77) return ['snow','Snow'];
  if(code<=82) return ['rain','Showers'];
  if(code<=86) return ['snow','Snow showers'];
  return ['storm','Thunderstorms'];
}
function weatherChip(w){
  if(!w||w.code==null) return '';
  const [icon,label]=weatherInfo(w.code);
  const temps=w.tmax!=null?` · ${Math.round(w.tmax)}° / ${Math.round(w.tmin)}°`:'';
  return `<span class="chip chip-weather" title="${label}${w.precip?`, ${w.precip} mm`:''}${w.wind?`, wind ${Math.round(w.wind)} km/h`:''}">${ico(icon)}${label}${temps}</span>`;
}

// ── Maps ─────────────────────────────────────────────────────────────────────
// Esri dark gray canvas: no API key needed (CARTO now requires one)
const ESRI='https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/';
function addBaseTiles(map){
  const opts={maxZoom:19,maxNativeZoom:16};
  L.tileLayer(ESRI+'World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',{...opts,attribution:'Tiles &copy; Esri &mdash; Esri, HERE, Garmin, &copy; OpenStreetMap contributors'}).addTo(map);
  L.tileLayer(ESRI+'World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',opts).addTo(map);
}
function pinStyle(r=8){return{radius:r,fillColor:'#0a84ff',color:'#fff',weight:2.5,opacity:1,fillOpacity:1};}
function photoPin(url,size=44){
  return L.divIcon({className:'photo-pin-wrap',iconSize:[size,size],iconAnchor:[size/2,size/2],
    html:`<div class="photo-pin" style="width:${size}px;height:${size}px;background-image:url('${url}')"></div>`});
}
function kmBetween(a,b){
  const R=6371,r=Math.PI/180,dLat=(b[0]-a[0])*r,dLng=(b[1]-a[1])*r;
  const h=Math.sin(dLat/2)**2+Math.cos(a[0]*r)*Math.cos(b[0]*r)*Math.sin(dLng/2)**2;
  return 2*R*Math.asin(Math.min(1,Math.sqrt(h)));
}
function cumulativeKm(pts){let d=0;return pts.map((p,i)=>i?(d+=kmBetween(pts[i-1],p)):0);}

// ── Route: map, elevation chart and replay ───────────────────────────────────
// `el` gets the map; `chartEl` (optional) gets the elevation chart.
function renderRoute(el,tracks,chartEl){
  const m=L.map(el,{zoomControl:true,attributionControl:false,scrollWheelZoom:false});
  addBaseTiles(m);
  const all=[], lines=[];
  tracks.forEach((t,i)=>{
    if(!t.points||!t.points.length) return;
    lines.push(L.polyline(t.points,{color:i===0?'#0a84ff':'#64d2ff',weight:4,opacity:.95,lineCap:'round',lineJoin:'round'}).addTo(m));
    const s=t.points[0], e=t.points[t.points.length-1];
    L.circleMarker(s,{radius:5,fillColor:'#30d158',color:'#fff',weight:2,fillOpacity:1}).addTo(m).bindTooltip('Start');
    L.circleMarker(e,{radius:5,fillColor:'#ff453a',color:'#fff',weight:2,fillOpacity:1}).addTo(m).bindTooltip('Finish');
    all.push(...t.points);
  });
  if(all.length) m.fitBounds(L.latLngBounds(all),{padding:[24,24]});
  const cursor=L.circleMarker([0,0],{radius:7,fillColor:'#fff',color:'#0a84ff',weight:3,fillOpacity:1});

  const main=tracks.find(t=>t.points&&t.points.length>1);
  let chart=null;
  if(chartEl&&main&&main.elevations&&main.elevations.length===main.points.length){
    chart=elevationChart(chartEl,main,i=>{
      if(i==null){m.removeLayer(cursor);return;}
      cursor.setLatLng(main.points[i]).addTo(m);
    });
  }

  // Replay: redraw the route from the start with a moving dot (and chart cursor)
  if(main){
    const btn=L.control({position:'topright'});
    btn.onAdd=()=>{
      const b=L.DomUtil.create('button','map-replay');
      b.innerHTML=`${ico('play')}<span>Replay</span>`;
      L.DomEvent.disableClickPropagation(b);
      b.onclick=()=>replay(b);
      return b;
    };
    btn.addTo(m);
  }
  let anim=null;
  function replay(b){
    if(anim){cancelAnimationFrame(anim.raf);anim.done();return;}
    const pts=main.points, dist=cumulativeKm(pts), total=dist[dist.length-1]||1;
    const dur=Math.min(9000,Math.max(4000,pts.length*12));
    lines.forEach(l=>l.setStyle({opacity:.22}));
    const trail=L.polyline([],{color:'#0a84ff',weight:5,opacity:1,lineCap:'round',lineJoin:'round'}).addTo(m);
    cursor.addTo(m); b.classList.add('playing'); b.querySelector('span').textContent='Stop';
    m.fitBounds(L.latLngBounds(pts),{padding:[24,24],animate:true});
    const t0=performance.now(); let k=0;
    anim={done(){anim=null;m.removeLayer(trail);m.removeLayer(cursor);lines.forEach(l=>l.setStyle({opacity:.95}));
      if(chart)chart.mark(null);b.classList.remove('playing');b.querySelector('span').textContent='Replay';}};
    const step=now=>{
      const f=Math.min(1,(now-t0)/dur), ease=f<.5?2*f*f:1-(-2*f+2)**2/2, target=ease*total;
      while(k<pts.length-1&&dist[k+1]<=target){k++;trail.addLatLng(pts[k]);}
      if(k===0&&!trail.getLatLngs().length) trail.addLatLng(pts[0]);
      cursor.setLatLng(pts[k]); if(chart) chart.mark(k);
      if(f<1) anim.raf=requestAnimationFrame(step); else setTimeout(()=>anim&&anim.done(),900);
    };
    anim.raf=requestAnimationFrame(step);
  }
  return m;
}

function elevationChart(el,track,onHover){
  const ele=track.elevations, dist=cumulativeKm(track.points), total=dist[dist.length-1]||1;
  const lo=Math.min(...ele), hi=Math.max(...ele), span=Math.max(hi-lo,20);
  const W=600,H=120,pad=6, x=d=>d/total*W, y=e=>H-pad-(e-lo)/span*(H-pad*2-10);
  const line=ele.map((e,i)=>`${i?'L':'M'}${x(dist[i]).toFixed(1)},${y(e).toFixed(1)}`).join('');
  el.innerHTML=`
    <div class="elev-head">
      <span>${ico('mountain')}Elevation</span>
      <span class="elev-stats">${track.ascent_m!=null?`<b>↑ ${fmtNum(track.ascent_m)} m</b>`:''}<b>${fmtNum(lo)}–${fmtNum(hi)} m</b><b>${fmtNum(total,1)} km</b></span>
    </div>
    <div class="elev-plot">
      <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
        <defs><linearGradient id="elev-g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0a84ff" stop-opacity=".55"/><stop offset="1" stop-color="#0a84ff" stop-opacity="0"/></linearGradient></defs>
        <path d="${line}L${W},${H}L0,${H}Z" fill="url(#elev-g)"/>
        <path d="${line}" fill="none" stroke="#0a84ff" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>
      </svg>
      <div class="elev-cursor" hidden><span></span></div>
    </div>`;
  const plot=el.querySelector('.elev-plot'), cur=el.querySelector('.elev-cursor'), lbl=cur.querySelector('span');
  function mark(i){
    if(i==null){cur.hidden=true;return;}
    cur.hidden=false;
    cur.style.left=`${dist[i]/total*100}%`;
    cur.style.setProperty('--y',`${y(ele[i])/H*100}%`);
    lbl.textContent=`${fmtNum(ele[i])} m · ${fmtNum(dist[i],1)} km`;
  }
  function at(ev){
    const r=plot.getBoundingClientRect(), cx=(ev.touches?ev.touches[0].clientX:ev.clientX)-r.left;
    const d=Math.max(0,Math.min(1,cx/r.width))*total;
    let i=0; while(i<dist.length-1&&dist[i+1]<d) i++;
    mark(i); onHover(i);
  }
  plot.addEventListener('mousemove',at); plot.addEventListener('touchmove',at,{passive:true});
  plot.addEventListener('touchstart',at,{passive:true});
  plot.addEventListener('mouseleave',()=>{mark(null);onHover(null);});
  plot.addEventListener('touchend',()=>{mark(null);onHover(null);});
  return {mark};
}

// ── Lightbox ─────────────────────────────────────────────────────────────────
function openLB(url,kind){
  const img=document.getElementById('lb-img'),vid=document.getElementById('lb-vid');
  img.hidden=kind==='video'; vid.hidden=kind!=='video';
  if(kind==='video'){vid.src=url;vid.play();}else img.src=url;
  document.getElementById('lightbox').classList.remove('hidden');
}
function wireLightbox(){
  document.getElementById('lb-vid').addEventListener('click',ev=>ev.stopPropagation());
  document.getElementById('lightbox').addEventListener('click',()=>{
    const vid=document.getElementById('lb-vid'); vid.pause(); vid.removeAttribute('src'); vid.load();
    document.getElementById('lb-img').removeAttribute('src');
    document.getElementById('lightbox').classList.add('hidden');
  });
}
function photoTile(p,extra=''){
  return p.kind==='video'
    ?`<video src="${p.url}#t=0.1" preload="metadata" muted playsinline></video><span class="photo-play">${ico('play')}</span>${extra}`
    :`<img src="${p.thumb_url||p.url}" alt="${esc(p.original_name||'')}" loading="lazy">${extra}`;
}
