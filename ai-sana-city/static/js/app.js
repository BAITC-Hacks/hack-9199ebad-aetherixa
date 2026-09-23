(function(){
  // ---------- Tabs ----------
  var tabs = document.querySelectorAll('.tab-btn');
  var views = document.querySelectorAll('.view');
  tabs.forEach(function(btn){
    btn.addEventListener('click', function(){
      tabs.forEach(function(b){ b.setAttribute('aria-selected','false'); });
      views.forEach(function(v){ v.classList.remove('active'); });
      btn.setAttribute('aria-selected','true');
      document.getElementById('view-' + btn.dataset.view).classList.add('active');
      window.scrollTo({top:0, behavior:'auto'});
    });
  });
  function goTo(view){
    var btn = document.querySelector('.tab-btn[data-view="'+view+'"]');
    if(btn) btn.click();
  }

  // ---------- City data ----------
  // Initial data is rendered by Flask into a non-executable JSON block.
  var dataNode = document.getElementById('initial-data');
  var appData = JSON.parse(dataNode.textContent);
  var buildings = appData.buildings;

  function stateText(p){
    if(p===0) return 'ждёт команду';
    if(p<50) return 'чертёж дополняется';
    if(p<90) return 'стройка идёт';
    return 'готово к старту';
  }

  // ---------- Isometric top-down city map ----------
  var ISO = {W:720, H:440, halfW:80, halfH:40, originX:360, originY:150, footW:120, footD:60};

  function isoAnchor(b){
    return { x: ISO.originX + (b.col - b.row) * ISO.halfW, y: ISO.originY + (b.col + b.row) * ISO.halfH };
  }
  function heightFor(p){ return p<=0 ? 0 : 40 + (p/100)*130; }
  function lerp(p1,p2,t){ return {x:p1.x+(p2.x-p1.x)*t, y:p1.y+(p2.y-p1.y)*t}; }
  function pt(p){ return p.x.toFixed(1)+','+p.y.toFixed(1); }

  function buildingGroup(b){
    var a = isoAnchor(b);
    var x=a.x, y=a.y, h=heightFor(b.percent);
    var fw=ISO.footW, fd=ISO.footD;
    var N={x:x,y:y-fd/2}, E={x:x+fw/2,y:y}, S={x:x,y:y+fd/2}, W={x:x-fw/2,y:y};
    var groundCls = b.percent===0 ? 'plot-empty' : 'plot-fill';
    var svg = '<polygon points="'+[N,E,S,W].map(pt).join(' ')+'" class="'+groundCls+'"/>';

    if(h>0){
      var topN={x:x,y:y-h-fd/2}, topE={x:x+fw/2,y:y-h}, topS={x:x,y:y-h+fd/2}, topW={x:x-fw/2,y:y-h};
      var leftPts=[topW,topS,S,W], rightPts=[topS,topE,E,S], topPts=[topN,topE,topS,topW];
      svg += '<polygon points="'+leftPts.map(pt).join(' ')+'" class="bld-left"/>';
      svg += '<polygon points="'+rightPts.map(pt).join(' ')+'" class="bld-right"/>';
      svg += '<polygon points="'+topPts.map(pt).join(' ')+'" class="bld-top'+(b.featured?' featured':'')+'"/>';

      var lit = Math.round(4 * b.percent/100);
      for(var i=0;i<4;i++){
        var t = 0.15 + i*0.22;
        var edgeA = lerp(S, topS, t), edgeB = lerp(E, topE, t);
        var c = lerp(edgeA, edgeB, 0.5);
        var cls = i<lit ? 'win-lit-iso' : 'win-dim-iso';
        svg += '<rect x="'+(c.x-4).toFixed(1)+'" y="'+(c.y-4).toFixed(1)+'" width="8" height="8" class="'+cls+'"/>';
      }

      if(b.percent>=90){
        var poleTop={x:topN.x,y:topN.y-26};
        svg += '<line x1="'+topN.x+'" y1="'+topN.y+'" x2="'+poleTop.x+'" y2="'+poleTop.y+'" class="flagpole"/>';
        svg += '<polygon points="'+poleTop.x+','+poleTop.y+' '+(poleTop.x+16)+','+(poleTop.y+5)+' '+poleTop.x+','+(poleTop.y+10)+'" class="flag"/>';
      }
    }
    var linked = b.view ? ' linked' : '';
    return '<g class="bld-group'+linked+'"'+(b.view?' data-view="'+b.view+'"':'')+'>'+svg+'</g>';
  }

  function markerAnchor(b){
    var a = isoAnchor(b);
    var h = heightFor(b.percent);
    var yTop = h>0 ? (a.y - h - ISO.footD/2 - (b.percent>=90?32:10)) : (a.y - ISO.footD/2 - 10);
    return { xPct: (a.x/ISO.W)*100, yPct: Math.max(3,(yTop/ISO.H)*100) };
  }

  function renderCityMap(){
    var svgEl = document.getElementById('isoSvg');
    var sorted = buildings.slice().sort(function(a,b){ return (a.col+a.row) - (b.col+b.row); });
    svgEl.innerHTML = sorted.map(buildingGroup).join('');
    svgEl.querySelectorAll('.bld-group.linked').forEach(function(g){
      g.addEventListener('click', function(){ goTo(g.dataset.view); });
    });

    var markerLayer = document.getElementById('mapMarkers');
    markerLayer.innerHTML = '';
    buildings.forEach(function(b){
      var m = markerAnchor(b);
      var el = document.createElement('div');
      el.className = 'map-marker' + (b.featured?' featured':'') + (b.view?'':' static');
      el.style.left = m.xPct + '%';
      el.style.top = m.yPct + '%';
      el.innerHTML = '<div class="marker-pin"><span class="m-name">'+b.icon+' '+b.name+'</span><span class="m-pct">'+b.percent+'/100 · '+stateText(b.percent)+'</span></div>';
      if(b.view){ el.addEventListener('click', function(){ goTo(b.view); }); }
      markerLayer.appendChild(el);
    });
  }

  // ---------- Task list mode ----------
  function renderCityList(){
    var list = document.getElementById('cityListMode');
    list.innerHTML = '';
    buildings.forEach(function(b){
      var row = document.createElement('div');
      row.className = 'task-row' + (b.featured?' featured':'') + (b.view?' linked':'');
      row.innerHTML = '<div class="task-icon">'+b.icon+'</div>'
        + '<div class="task-row-main"><div class="task-row-name">'+b.name+'</div><div class="task-row-quest">'+b.quest+'</div></div>'
        + '<div class="task-row-progress"><div class="readiness-bar"><div class="readiness-fill" style="width:'+b.percent+'%"></div></div><div class="task-row-pct">'+b.percent+' / 100</div></div>'
        + '<div class="task-row-state">'+stateText(b.percent)+'</div>';
      if(b.view){ row.addEventListener('click', function(){ goTo(b.view); }); }
      list.appendChild(row);
    });
  }

  renderCityMap();
  renderCityList();

  // ---------- Map / list toggle ----------
  var toggleBtns = document.querySelectorAll('.toggle-btn');
  toggleBtns.forEach(function(btn){
    btn.addEventListener('click', function(){
      toggleBtns.forEach(function(b){ b.classList.remove('active'); });
      btn.classList.add('active');
      var mode = btn.dataset.mode;
      document.getElementById('cityMapMode').style.display = mode==='map' ? '' : 'none';
      document.getElementById('cityListMode').style.display = mode==='list' ? '' : 'none';
    });
  });

  // ---------- Path-choice chips ----------
  document.querySelectorAll('#choiceChips .chip').forEach(function(chip){
    chip.addEventListener('click', function(){
      document.querySelectorAll('#choiceChips .chip').forEach(function(c){ c.classList.remove('selected'); });
      chip.classList.add('selected');
    });
  });

  // ---------- Hint depth ----------
  var hintLevel = 0;
  var hintTexts = appData.hints;
  var hintLabels = appData.hint_labels;
  var hintBtn = document.getElementById('hintBtn');
  var hintLevels = document.getElementById('hintLevels');
  hintBtn.addEventListener('click', function(){
    if(hintLevel >= hintTexts.length){ return; }
    var p = document.createElement('p');
    p.textContent = hintTexts[hintLevel];
    hintLevels.appendChild(p);
    hintLevel++;
    hintBtn.textContent = hintLabels[Math.min(hintLevel, hintLabels.length-1)];
    if(hintLevel >= hintTexts.length){ hintBtn.disabled = true; hintBtn.style.opacity = 0.5; }
  });

  // ---------- Boss checklist ----------
  var criteria = document.querySelectorAll('.criterion');
  var bossCount = document.getElementById('bossCount');
  var celebration = document.getElementById('celebration');

  function updateBoss(){
    var confirmed = document.querySelectorAll('.criterion.confirmed').length;
    bossCount.textContent = confirmed + ' / ' + criteria.length + ' подтверждено';
    if(confirmed === criteria.length){
      celebration.classList.add('show');
    } else {
      celebration.classList.remove('show');
    }
  }

  criteria.forEach(function(item){
    if(!item.classList.contains('confirmed')){
      item.addEventListener('click', function(){
        item.classList.toggle('confirmed');
        var box = item.querySelector('.crit-box');
        box.textContent = item.classList.contains('confirmed') ? '✓' : '';
        var seg = document.querySelector('.boss-seg[data-idx="'+item.dataset.idx+'"]');
        if(seg) seg.classList.toggle('confirmed');
        updateBoss();
      });
      item.addEventListener('keydown', function(e){
        if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); item.click(); }
      });
    }
  });
})();
