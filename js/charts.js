const Charts = {
  instances: {},

  palette(){
    return {
      fg: '#e4ded3',
      dim: '#aaa095',
      faint: '#77736e',
      line: '#363636',
      accent: '#83b9e8',
      shades: ['#e4ded3','#d0c8bd','#c3a895','#d8b17f','#d98a86','#83b9e8']
    };
  },

  baseOptions(overrides={}){
    const p = this.palette();
    return Object.assign({
      responsive:true,
      maintainAspectRatio:false,
      animation:{ duration:600, easing:'easeOutQuart' },
      plugins:{
        legend:{ labels:{ color:p.dim, font:{family:'ui-monospace, monospace', size:10.5}, boxWidth:10, padding:14 } },
        tooltip:{ backgroundColor:'#131313', borderColor:p.line, borderWidth:1, titleColor:p.fg, bodyColor:p.dim, titleFont:{family:'ui-monospace, monospace'}, bodyFont:{family:'ui-monospace, monospace'} }
      },
      scales:{}
    }, overrides);
  },

  axisDefaults(){
    const p = this.palette();
    return {
      grid:{ color:p.line, drawTicks:false },
      ticks:{ color:p.faint, font:{family:'ui-monospace, monospace', size:10} },
      border:{ color:p.line }
    };
  },

  destroy(id){
    if(this.instances[id]){ this.instances[id].destroy(); delete this.instances[id]; }
  },

  makeCanvas(container){
    container.innerHTML = '<div class="chart-wrap"><canvas></canvas></div>';
    return container.querySelector('canvas');
  },

  pie(container, id, labels, data){
    const canvas = this.makeCanvas(container);
    this.destroy(id);
    const p = this.palette();
    this.instances[id] = new Chart(canvas, {
      type:'doughnut',
      data:{ labels, datasets:[{ data, backgroundColor:p.shades, borderColor:'#1e1e1e', borderWidth:2 }] },
      options: this.baseOptions({ cutout:'62%' })
    });
  },

  bar(container, id, labels, data, opts={}){
    const canvas = this.makeCanvas(container);
    this.destroy(id);
    const p = this.palette();
    this.instances[id] = new Chart(canvas, {
      type:'bar',
      data:{ labels, datasets:[{ label:opts.label||'', data, backgroundColor:p.fg, borderRadius:4, maxBarThickness:34 }] },
      options: this.baseOptions({
        plugins:{ legend:{ display: !!opts.label, labels:this.baseOptions().plugins.legend.labels }, tooltip: this.baseOptions().plugins.tooltip },
        scales:{ x:this.axisDefaults(), y: Object.assign(this.axisDefaults(), {beginAtZero:true}) }
      })
    });
  },

  line(container, id, labels, datasets, opts={}){
    const canvas = this.makeCanvas(container);
    this.destroy(id);
    const p = this.palette();
    this.instances[id] = new Chart(canvas, {
      type:'line',
      data:{ labels, datasets: datasets.map((d,i)=>({
        label:d.label, data:d.data, borderColor: i===0?p.fg:p.accent, backgroundColor: opts.area ? (i===0? 'rgba(228,222,211,.12)':'rgba(131,185,232,.12)') : 'transparent',
        fill: !!opts.area, tension:.35, pointRadius:2, pointBackgroundColor: i===0?p.fg:p.accent, borderWidth:2
      })) },
      options: this.baseOptions({ scales:{ x:this.axisDefaults(), y:Object.assign(this.axisDefaults(),{beginAtZero:true}) } })
    });
  },

  groupedBar(container, id, labels, datasets){
    const canvas = this.makeCanvas(container);
    this.destroy(id);
    const p = this.palette();
    this.instances[id] = new Chart(canvas, {
      type:'bar',
      data:{ labels, datasets: datasets.map((d,i)=>({ label:d.label, data:d.data, backgroundColor: i===0?p.fg:p.accent, borderRadius:4, maxBarThickness:26 })) },
      options: this.baseOptions({ scales:{ x:this.axisDefaults(), y:Object.assign(this.axisDefaults(),{beginAtZero:true}) } })
    });
  }
};