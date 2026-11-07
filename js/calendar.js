const Calendar = {
  state: { view: 'month', cursor: new Date() },

  DOW: ['SUN','MON','TUE','WED','THU','FRI','SAT'],

  setView(v){ this.state.view = v; },

  shift(dir){
    const c = this.state.cursor;
    if(this.state.view==='day') this.state.cursor = Utils.addDays(c, dir);
    else if(this.state.view==='week') this.state.cursor = Utils.addDays(c, dir*7);
    else if(this.state.view==='month') this.state.cursor = new Date(c.getFullYear(), c.getMonth()+dir, 1);
    else if(this.state.view==='year') this.state.cursor = new Date(c.getFullYear()+dir, c.getMonth(), 1);
  },

  goToday(){ this.state.cursor = new Date(); },

  title(){
    const c = this.state.cursor;
    if(this.state.view==='day') return c.toLocaleDateString(undefined,{month:'short', day:'numeric', year:'numeric'});
    if(this.state.view==='week'){
      const start = this.startOfWeek(c);
      const end = Utils.addDays(start,6);
      return `${Utils.fmtDateShort(start)} - ${Utils.fmtDateShort(end)}`;
    }
    if(this.state.view==='month') return `${Utils.monthName(c.getMonth())} ${c.getFullYear()}`;
    if(this.state.view==='year') return `${c.getFullYear()}`;
  },

  startOfWeek(d){
    const day = d.getDay();
    return Utils.addDays(d, -day);
  },

  toolbarHtml(){
    const v = this.state.view;
    const btn = (id,label) => `<button class="chip ${v===id?'selected':''}" data-calview="${id}">${label}</button>`;
    return `
      <div class="cal-toolbar">
        <div class="cal-views">
          ${btn('day','DAY')}${btn('week','WEEK')}${btn('month','MONTH')}${btn('year','YEAR')}
        </div>
        <div class="cal-nav">
          <button class="btn btn-sm" data-calnav="-1">&lt;</button>
          <span class="cal-title">${this.title()}</span>
          <button class="btn btn-sm" data-calnav="1">&gt;</button>
          <button class="btn btn-sm" data-calnav="0">TODAY</button>
        </div>
      </div>`;
  },

  render(container, opts){
    this._container = container;
    this._opts = opts;
    container.innerHTML = this.toolbarHtml() + '<div id="calBody"></div>';
    container.querySelectorAll('[data-calview]').forEach(b=>{
      b.addEventListener('click', ()=>{ this.setView(b.dataset.calview); this.render(container, opts); });
    });
    container.querySelectorAll('[data-calnav]').forEach(b=>{
      b.addEventListener('click', ()=>{
        const d = parseInt(b.dataset.calnav,10);
        if(d===0) this.goToday(); else this.shift(d);
        this.render(container, opts);
      });
    });
    const body = container.querySelector('#calBody');
    if(this.state.view==='day') this.renderDay(body, opts);
    else if(this.state.view==='week') this.renderWeek(body, opts);
    else if(this.state.view==='month') this.renderMonth(body, opts);
    else this.renderYear(body, opts);
  },

  cellClass(dateStr, opts){
    const info = opts.getDayInfo(dateStr) || {};
    const today = Utils.todayStr();
    let cls = 'cal-cell';
    if(dateStr === today) cls += ' today';
    if(dateStr > today) cls += ' future';
    if(info.status === 'completed' || info.status === 'partial') cls += ' contributed';
    if(info.status === 'missed') cls += ' missed';
    return { cls, info };
  },

  tooltipHtml(dateStr, info, opts){
    if(!info) return 'No entry';
    const parts = [];
    if(info.amount) parts.push(`Saved ${Utils.fmtMoney(info.amount)}`);
    if(info.notes) parts.push(info.notes);
    if(opts.remainingAt) parts.push(`Remaining ${Utils.fmtMoney(opts.remainingAt(dateStr))}`);
    return parts.join(' · ') || 'No entry';
  },

  dayCellHtml(dateStr, opts, dayNum){
    const { cls, info } = this.cellClass(dateStr, opts);
    const tip = this.tooltipHtml(dateStr, info, opts);
    return `<div class="${cls}" data-date="${dateStr}">
      <span class="cal-daynum">${dayNum}</span>
      <div class="cal-tooltip">${Utils.escapeHtml(tip)}</div>
    </div>`;
  },

  bindCellClicks(container, opts){
    container.querySelectorAll('.cal-cell[data-date]').forEach(cell=>{
      cell.addEventListener('click', ()=> opts.onDayClick(cell.dataset.date));
    });
  },

  renderMonth(body, opts){
    const c = this.state.cursor;
    const year = c.getFullYear(), month = c.getMonth();
    const first = new Date(year, month, 1);
    const startOffset = first.getDay();
    const daysInMonth = new Date(year, month+1, 0).getDate();
    let html = '<div class="cal-grid">';
    this.DOW.forEach(d => html += `<div class="cal-dow">${d}</div>`);
    for(let i=0;i<startOffset;i++) html += '<div class="cal-cell empty"></div>';
    for(let d=1; d<=daysInMonth; d++){
      const dateStr = Utils.dateStr(new Date(year,month,d));
      html += this.dayCellHtml(dateStr, opts, d);
    }
    html += '</div>';
    body.innerHTML = html;
    this.bindCellClicks(body, opts);
  },

  renderWeek(body, opts){
    const start = this.startOfWeek(this.state.cursor);
    let html = '<div class="cal-grid">';
    this.DOW.forEach(d => html += `<div class="cal-dow">${d}</div>`);
    for(let i=0;i<7;i++){
      const d = Utils.addDays(start,i);
      const dateStr = Utils.dateStr(d);
      html += this.dayCellHtml(dateStr, opts, d.getDate());
    }
    html += '</div>';
    body.innerHTML = html;
    this.bindCellClicks(body, opts);
  },

  renderDay(body, opts){
    const dateStr = Utils.dateStr(this.state.cursor);
    const info = opts.getDayInfo(dateStr) || {};
    const tip = this.tooltipHtml(dateStr, info, opts);
    body.innerHTML = `
      <div class="cal-week-row" style="flex-direction:column; align-items:flex-start; gap:10px; padding:24px;">
        <div style="font-size:15px;">${Utils.fmtDateHuman(dateStr)}</div>
        <div class="mono-dim" style="font-size:12.5px;">${Utils.escapeHtml(tip)}</div>
        <button class="btn btn-primary btn-sm" data-date="${dateStr}">OPEN DAY</button>
      </div>`;
    body.querySelector('[data-date]').addEventListener('click', ()=> opts.onDayClick(dateStr));
  },

  renderYear(body, opts){
    const year = this.state.cursor.getFullYear();
    let html = '<div class="cal-year-grid">';
    for(let m=0;m<12;m++){
      const daysInMonth = new Date(year, m+1, 0).getDate();
      let contributed = 0, missed = 0;
      for(let d=1; d<=daysInMonth; d++){
        const info = opts.getDayInfo(Utils.dateStr(new Date(year,m,d)));
        if(info){
          if(info.status==='completed' || info.status==='partial') contributed++;
          if(info.status==='missed') missed++;
        }
      }
      html += `<div class="cal-year-month" data-month="${m}" style="cursor:pointer; flex-direction:column; align-items:flex-start; gap:6px;">
        <strong style="font-size:12.5px;">${Utils.monthName(m).slice(0,3).toUpperCase()}</strong>
        <span class="mono-dim" style="font-size:10.5px;">${contributed} saved · ${missed} missed</span>
      </div>`;
    }
    html += '</div>';
    body.innerHTML = html;
    body.querySelectorAll('[data-month]').forEach(el=>{
      el.addEventListener('click', ()=>{
        this.state.cursor = new Date(year, parseInt(el.dataset.month,10), 1);
        this.state.view = 'month';
        this.render(this._container, this._opts);
      });
    });
  }
};