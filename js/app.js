const STORAGE_KEY = 'asciiBudgetData_v1';

const Utils = {
  uid(){ return Date.now().toString(36) + Math.random().toString(36).slice(2,8); },
  pad(n){ return n.toString().padStart(2,'0'); },
  dateStr(d){ return `${d.getFullYear()}-${Utils.pad(d.getMonth()+1)}-${Utils.pad(d.getDate())}`; },
  todayStr(){ return Utils.dateStr(new Date()); },
  parseDate(s){ const [y,m,d] = s.split('-').map(Number); return new Date(y, m-1, d); },
  addDays(date, n){ const d = new Date(date); d.setDate(d.getDate()+n); return d; },
  daysBetween(a,b){ const MS = 86400000; const da = new Date(a.getFullYear(),a.getMonth(),a.getDate()); const db = new Date(b.getFullYear(),b.getMonth(),b.getDate()); return Math.round((db-da)/MS); },
  fmtMoney(n){
    const sym = Store.state.settings.currency || '₱';
    const sign = n < 0 ? '-' : '';
    n = Math.abs(n || 0);
    return `${sign}${sym}${n.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}`;
  },
  fmtDateHuman(s){
    const d = typeof s === 'string' ? Utils.parseDate(s) : s;
    return d.toLocaleDateString(undefined,{month:'short', day:'numeric', year:'numeric'});
  },
  fmtDateShort(s){
    const d = typeof s === 'string' ? Utils.parseDate(s) : s;
    return d.toLocaleDateString(undefined,{month:'short', day:'numeric'});
  },
  monthName(m){ return ['January','February','March','April','May','June','July','August','September','October','November','December'][m]; },
  clamp(n,min,max){ return Math.max(min, Math.min(max,n)); },
  escapeHtml(s){ const d = document.createElement('div'); d.textContent = s ?? ''; return d.innerHTML; },
  debounce(fn, wait){ let t; return (...a)=>{ clearTimeout(t); t = setTimeout(()=>fn(...a), wait); }; },
  progressBar(pct){
    const value = Math.round(Utils.clamp(pct,0,100));
    return `<div class="progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${value}" aria-valuetext="${value}%"><span style="width:${value}%"></span></div><span class="progress-value">${value}%</span>`;
  }
};

const Store = {
  state: null,
  defaults(){
    return {
      settings: { currency:'₱', theme:'dark' },
      categories: ['Food','Transport','School','Shopping','Entertainment','Subscriptions','Utilities','Healthcare','Miscellaneous'],
      goals: [],
      expenses: [],
      budgetConfig: { type:'monthly', amount:8000 },
      debts: [],
      activity: [],
      deleted: []
    };
  },
  load(){
    try{
      const raw = localStorage.getItem(STORAGE_KEY);
      this.state = raw ? Object.assign(this.defaults(), JSON.parse(raw)) : this.defaults();
      if(!this.state.categories) this.state.categories = this.defaults().categories;
    }catch(e){
      console.error('Store load failed', e);
      this.state = this.defaults();
    }
  },
  save(){
    localStorage.setItem(STORAGE_KEY, JSON.stringify(this.state));
    Core.pulseAutosave();
  },
  logActivity(text, type='info'){
    this.state.activity.unshift({ id: Utils.uid(), text, type, ts: Date.now() });
    this.state.activity = this.state.activity.slice(0,60);
  }
};

const Toast = {
  show(msg, opts={}){
    const stack = document.getElementById('toastStack');
    const el = document.createElement('div');
    el.className = 'toast' + (opts.warn ? ' warn' : '');
    el.innerHTML = `<span>${Utils.escapeHtml(msg)}</span>`;
    if(opts.undo){
      const btn = document.createElement('button');
      btn.className = 'btn btn-sm btn-ghost';
      btn.textContent = 'UNDO';
      btn.style.marginLeft = 'auto';
      btn.onclick = () => { opts.undo(); el.remove(); };
      el.appendChild(btn);
    }
    stack.appendChild(el);
    setTimeout(()=>{
      el.classList.add('out');
      setTimeout(()=>el.remove(), 260);
    }, opts.duration || 4200);
  }
};

const Modal = {
  open(title, bodyHtml, opts={}){
    const root = document.getElementById('modalRoot');
    const box = document.getElementById('modalBox');
    box.innerHTML = `
      <div class="modal-head">
        <div class="modal-title">${title}</div>
        <button class="modal-close" id="modalCloseBtn">×</button>
      </div>
      <div id="modalBody">${bodyHtml}</div>
    `;
    root.classList.remove('hidden');
    document.getElementById('modalCloseBtn').onclick = () => Modal.close();
    document.querySelector('.modal-backdrop').onclick = () => Modal.close();
    if(opts.onOpen) opts.onOpen(box);
    Modal._escHandler = (e) => { if(e.key==='Escape') Modal.close(); };
    document.addEventListener('keydown', Modal._escHandler);
  },
  close(){
    document.getElementById('modalRoot').classList.add('hidden');
    if(Modal._escHandler) document.removeEventListener('keydown', Modal._escHandler);
  },
  confirm(message, onConfirm, opts={}){
    Modal.open(opts.title || 'Confirm', `
      <p style="font-size:13px; color:var(--fg-dim); margin-bottom:20px;">${Utils.escapeHtml(message)}</p>
      <div class="modal-foot">
        <button class="btn" id="confCancel">Cancel</button>
        <button class="btn ${opts.danger ? 'btn-danger' : 'btn-primary'}" id="confOk">${opts.okLabel || 'Confirm'}</button>
      </div>
    `);
    document.getElementById('confCancel').onclick = () => Modal.close();
    document.getElementById('confOk').onclick = () => { onConfirm(); Modal.close(); };
  }
};

const Core = {
  currentView: 'dashboard',
  renderers: {},

  boot(){
    Store.load();
    document.body.dataset.theme = Store.state.settings.theme;
    this.wireNav();
    this.wireSearch();
    this.wireQuickAdd();
    this.wireKeyboard();
    this.tickClock();
    this.renderAll();
  },

  tickClock(){
    const el = document.getElementById('todayDate');
    const now = new Date();
    el.textContent = now.toLocaleDateString(undefined,{weekday:'long', month:'long', day:'numeric', year:'numeric'});
  },

  pulseAutosave(){
    const el = document.getElementById('autosaveIndicator');
    el.textContent = 'Saving…';
    el.classList.add('pulse');
    clearTimeout(this._autosaveTimer);
    this._autosaveTimer = setTimeout(()=>{
      el.textContent = 'Saved';
      el.classList.remove('pulse');
    }, 500);
  },

  wireNav(){
    const tabs = [...document.querySelectorAll('[role="tab"][data-view]')];
    tabs.forEach((tab,index)=>{
      tab.addEventListener('click', ()=> this.goTo(tab.dataset.view));
      tab.addEventListener('keydown', event=>{
        let nextIndex;
        if(event.key === 'ArrowRight') nextIndex = (index + 1) % tabs.length;
        if(event.key === 'ArrowLeft') nextIndex = (index - 1 + tabs.length) % tabs.length;
        if(event.key === 'Home') nextIndex = 0;
        if(event.key === 'End') nextIndex = tabs.length - 1;
        if(nextIndex === undefined) return;
        event.preventDefault();
        tabs[nextIndex].focus();
        this.goTo(tabs[nextIndex].dataset.view);
      });
    });
  },

  goTo(view){
    this.currentView = view;
    document.querySelectorAll('[role="tab"][data-view]').forEach(tab=>{
      const active = tab.dataset.view === view;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active', v.id === 'view-'+view));
    this.render(view);
  },

  wireQuickAdd(){
    const btn = document.getElementById('quickAddBtn');
    const menu = document.getElementById('quickAddMenu');
    const closeMenu = ()=>{
      menu.classList.add('hidden');
      btn.setAttribute('aria-expanded','false');
    };
    btn.addEventListener('click', event=>{
      event.stopPropagation();
      const open = menu.classList.toggle('hidden') === false;
      btn.setAttribute('aria-expanded', String(open));
    });
    document.addEventListener('click', event=>{
      if(!menu.contains(event.target) && event.target !== btn) closeMenu();
    });
    menu.querySelectorAll('button').forEach(b=>{
      b.addEventListener('click', (e)=>{
        e.stopPropagation();
        closeMenu();
        const kind = b.dataset.quick;
        if(kind==='expense') Budget.openExpenseModal();
        if(kind==='goal') Savings.openGoalModal();
        if(kind==='debt') Debt.openDebtModal();
        if(kind==='contribution') Savings.openQuickContribution();
      });
    });
  },

  wireKeyboard(){
    document.addEventListener('keydown', (e)=>{
      const tag = (e.target.tagName || '').toLowerCase();
      const typing = tag==='input' || tag==='textarea' || tag==='select';
      if(e.key === '/' && !typing){ e.preventDefault(); document.getElementById('globalSearch').focus(); }
      if(e.key === 'Escape'){
        document.getElementById('quickAddMenu').classList.add('hidden');
        document.getElementById('quickAddBtn').setAttribute('aria-expanded','false');
        Modal.close();
      }
      if(typing) return;
      if(e.key.toLowerCase() === 'q'){
        const menu = document.getElementById('quickAddMenu');
        const open = menu.classList.toggle('hidden') === false;
        document.getElementById('quickAddBtn').setAttribute('aria-expanded', String(open));
      }
      if(e.key === '1') this.goTo('dashboard');
      if(e.key === '2') this.goTo('savings');
      if(e.key === '3') this.goTo('budget');
      if(e.key === '4') this.goTo('debt');
      if(e.key === '5') this.goTo('analytics');
      if(e.key === '6') this.goTo('settings');
    });
  },

  wireSearch(){
    const input = document.getElementById('globalSearch');
    const results = document.getElementById('searchResults');
    const run = Utils.debounce((q)=>{
      if(!q.trim()){ results.classList.add('hidden'); results.innerHTML=''; return; }
      const items = Search.query(q);
      results.classList.remove('hidden');
      if(!items.length){ results.innerHTML = '<div class="sr-empty">NO MATCHES FOUND</div>'; return; }
      results.innerHTML = items.map(it => `
        <div class="sr-item" data-view="${it.view}">
          <span>${Utils.escapeHtml(it.label)}</span>
          <span class="sr-tag">${it.tag}</span>
        </div>`).join('');
      results.querySelectorAll('.sr-item').forEach((el,i)=>{
        el.addEventListener('click', ()=>{ Core.goTo(items[i].view); results.classList.add('hidden'); input.value=''; });
      });
    }, 200);
    input.addEventListener('input', (e)=> run(e.target.value));
    input.addEventListener('focus', ()=>{ if(input.value.trim()) results.classList.remove('hidden'); });
    document.addEventListener('click', (e)=>{
      if(!results.contains(e.target) && e.target !== input) results.classList.add('hidden');
    });
  },

  renderAll(){
    Dashboard.render();
    Savings.render();
    Budget.render();
    Debt.render();
    Analytics.render();
    Settings.render();
  },

  render(view){
    if(view === 'dashboard') Dashboard.render();
    if(view === 'savings') Savings.render();
    if(view === 'budget') Budget.render();
    if(view === 'debt') Debt.render();
    if(view === 'analytics') Analytics.render();
    if(view === 'settings') Settings.render();
  },

  refreshAllData(){
    Store.save();
    this.renderAll();
  }
};

const Search = {
  query(q){
    q = q.toLowerCase();
    const out = [];
    const s = Store.state;
    s.goals.forEach(g=>{ if(g.name.toLowerCase().includes(q)) out.push({label:g.name, tag:'GOAL', view:'savings'}); });
    s.expenses.forEach(e=>{
      if(e.title.toLowerCase().includes(q) || e.category.toLowerCase().includes(q) || (e.notes||'').toLowerCase().includes(q))
        out.push({label:`${e.title} — ${Utils.fmtMoney(e.amount)}`, tag:'EXPENSE', view:'budget'});
    });
    s.debts.forEach(d=>{
      if(d.borrower.toLowerCase().includes(q) || (d.notes||'').toLowerCase().includes(q))
        out.push({label:`${d.borrower} — ${Utils.fmtMoney(d.amount)}`, tag:Debt.isOwedToYou(d)?'OWED TO YOU':'YOU OWE', view:'debt'});
    });
    s.categories.forEach(c=>{ if(c.toLowerCase().includes(q)) out.push({label:c, tag:'CATEGORY', view:'budget'}); });
    return out.slice(0,20);
  }
};

const Dashboard = {
  totalSavings(){ return Store.state.goals.reduce((s,g)=> s + Savings.savedAmount(g), 0); },

  upcomingGoal(){
    const active = Store.state.goals.filter(g => Savings.progressPct(g) < 100);
    if(!active.length) return null;
    return active.sort((a,b)=> a.targetDate.localeCompare(b.targetDate))[0];
  },

  ring(pct, label, sub){
    const r = 34, c = 2*Math.PI*r;
    const off = c - (Utils.clamp(pct,0,100)/100)*c;
    return `
      <div class="ring-wrap">
        <svg width="86" height="86">
          <circle class="ring-bg" cx="43" cy="43" r="${r}"></circle>
          <circle class="ring-fg" cx="43" cy="43" r="${r}" stroke-dasharray="${c}" stroke-dashoffset="${off}"></circle>
        </svg>
        <span class="ring-label">${Math.round(pct)}%</span>
      </div>
      <div style="text-align:center; margin-top:8px;">
        <div style="font-size:11.5px;">${label}</div>
        <div class="mono-dim" style="font-size:10.5px;">${sub||''}</div>
      </div>`;
  },

  render(){
    const el = document.getElementById('view-dashboard');
    const now = new Date();
    const totalDebtOwed = Store.state.debts.filter(d=>Debt.isOwedToYou(d)).reduce((s,d)=>s+Debt.currentOwed(d),0);
    const goal = this.upcomingGoal();
    const health = Budget.healthScore();
    const recent = Store.state.activity.slice(0,8);

    el.innerHTML = `
      <div class="section-head">
        <div>
          <div class="section-title">Dashboard</div>
          <div class="section-sub">${Utils.monthName(now.getMonth())} ${now.getFullYear()} &middot; ${now.toLocaleDateString(undefined,{weekday:'long', month:'long', day:'numeric'})}</div>
        </div>
        <div class="btn-row">
          <button class="btn btn-primary" data-qa="expense">+ EXPENSE</button>
          <button class="btn" data-qa="contribution">+ SAVE</button>
          <button class="btn" data-qa="debt">+ DEBT</button>
        </div>
      </div>

      <div class="grid grid-4" style="margin-bottom:var(--gap);">
        <div class="card"><div class="card-label">Current Savings</div><div class="card-value">${Utils.fmtMoney(this.totalSavings())}</div><div class="card-sub">across ${Store.state.goals.length} goal(s)</div></div>
        <div class="card"><div class="card-label">Remaining Budget</div><div class="card-value">${Utils.fmtMoney(Budget.remainingBudget())}</div><div class="card-sub">${Store.state.budgetConfig.type} plan</div></div>
        <div class="card"><div class="card-label">Owed to You</div><div class="card-value">${Utils.fmtMoney(totalDebtOwed)}</div><div class="card-sub">You owe ${Utils.fmtMoney(Store.state.debts.filter(d=>!Debt.isOwedToYou(d)).reduce((s,d)=>s+Debt.currentOwed(d),0))} · ${Store.state.debts.filter(d=>Debt.effectiveStatus(d)==='overdue').length} overdue</div></div>
        <div class="card"><div class="card-label">Weekly / Monthly Spend</div><div class="card-value" style="font-size:20px;">${Utils.fmtMoney(Budget.spentThisWeek())}</div><div class="card-sub">${Utils.fmtMoney(Budget.spentThisMonth())} this month</div></div>
      </div>

      <div class="grid grid-3" style="margin-bottom:var(--gap);">
        <div class="card" style="display:flex; flex-direction:column; align-items:center;">
          ${this.ring(health, 'BUDGET HEALTH', `${health}/100`)}
        </div>
        <div class="card" style="display:flex; flex-direction:column; align-items:center;">
          ${goal ? this.ring(Savings.progressPct(goal), goal.name.toUpperCase(), Utils.fmtDateShort(goal.targetDate)) : this.ring(0,'NO ACTIVE GOAL','create one')}
        </div>
        <div class="card">
          <div class="card-label" style="margin-bottom:10px;">7-Day Spending</div>
          <div id="dashMiniChart"></div>
        </div>
      </div>

      <div class="grid grid-2">
        <div class="card">
          <div class="card-label" style="margin-bottom:12px;">Upcoming Goal</div>
          ${goal ? `
            <div style="font-size:15px; margin-bottom:6px;">${Utils.escapeHtml(goal.name)}</div>
            <div class="progress-wrap" style="margin-bottom:8px;">${Utils.progressBar(Savings.progressPct(goal))}</div>
            <div class="card-sub">${Utils.fmtMoney(Savings.remainingAmount(goal))} remaining &middot; ${Savings.remainingDays(goal)} days left</div>
          ` : `<div class="card-sub">No active goals. Create one from the Savings Goals tab.</div>`}
        </div>
        <div class="card">
          <div class="card-label" style="margin-bottom:12px;">Recent Activity</div>
          ${recent.length ? `<div class="list">${recent.map(a=>`
            <div class="list-row"><span class="lr-title" style="font-size:12px;">${Utils.escapeHtml(a.text)}</span><span class="lr-meta">${new Date(a.ts).toLocaleDateString(undefined,{month:'short',day:'numeric'})}</span></div>
          `).join('')}</div>` : `<div class="card-sub">No activity yet — start by adding an expense or goal.</div>`}
        </div>
      </div>
    `;
    el.querySelectorAll('[data-qa]').forEach(b=>{
      b.addEventListener('click', ()=>{
        const kind = b.dataset.qa;
        if(kind==='expense') Budget.openExpenseModal();
        if(kind==='contribution') Savings.openQuickContribution();
        if(kind==='debt') Debt.openDebtModal();
      });
    });
    const week = Budget.weeklySeries();
    Charts.bar(document.getElementById('dashMiniChart'), 'dashMini', week.labels, week.data);
  }
};

const Analytics = {
  savingsRate(){
    const saved = Dashboard.totalSavings();
    const spent = Budget.totalSpentAllTime();
    const total = saved + spent;
    return total > 0 ? (saved/total)*100 : 0;
  },
  budgetAccuracy(){
    const cfg = Store.state.budgetConfig;
    const projected = Budget.projectedEndOfPeriod();
    if(!cfg.amount) return 0;
    return Utils.clamp(100 - (Math.abs(projected-cfg.amount)/cfg.amount)*100, 0, 100);
  },
  collectionRate(){
    const debts = Store.state.debts.filter(d=>Debt.isOwedToYou(d));
    if(!debts.length) return 0;
    const total = debts.reduce((s,d)=>s+Debt.totalCollectable(d),0);
    const collected = debts.reduce((s,d)=>s+Debt.totalPaid(d),0);
    return total>0 ? (collected/total)*100 : 0;
  },
  savingsConsistency(){
    if(!Store.state.goals.length) return 0;
    const rates = Store.state.goals.map(g=>Savings.successRate(g));
    return (rates.reduce((a,b)=>a+b,0)/rates.length)*100;
  },
  projectedYearEndSavings(){
    const now = new Date();
    const daysLeft = Utils.daysBetween(now, new Date(now.getFullYear(),11,31));
    let dailyRate = 0;
    Store.state.goals.forEach(g=>{ dailyRate += Savings.averageContribution(g) / Savings.periodDays(g.method, g.customDays); });
    return Dashboard.totalSavings() + dailyRate*daysLeft;
  },
  projectedDebtCollection(){
    return Store.state.debts.filter(d=>Debt.isOwedToYou(d)&&d.status!=='paid').reduce((s,d)=>s+Debt.currentOwed(d),0);
  },
  heatmapData(){
    const map = {};
    Store.state.goals.forEach(g=> Object.entries(g.entries||{}).forEach(([date,e])=>{
      if(e.status==='completed'||e.status==='partial') map[date] = (map[date]||0) + 1;
    }));
    return map;
  },
  insights(){
    const out = [];
    const cat = Budget.categoryTotals();
    const now = new Date();
    const thisMonthTotal = Budget.spentInRange(new Date(now.getFullYear(),now.getMonth(),1), new Date(now.getFullYear(),now.getMonth()+1,0));
    const lastMonthStart = new Date(now.getFullYear(), now.getMonth()-1, 1);
    const lastMonthEnd = new Date(now.getFullYear(), now.getMonth(), 0);
    const lastMonthTotal = Budget.spentInRange(lastMonthStart, lastMonthEnd);
    if(lastMonthTotal > 0){
      const diff = ((thisMonthTotal-lastMonthTotal)/lastMonthTotal)*100;
      out.push(`You are ${diff<=0?Math.abs(diff).toFixed(0)+'% under':diff.toFixed(0)+'% over'} last month's spending pace.`);
    }
    const goal = Dashboard.upcomingGoal();
    if(goal){
      const est = Savings.estimatedCompletion(goal);
      const target = Utils.parseDate(goal.targetDate);
      if(est){
        const diffDays = Utils.daysBetween(est, target);
        if(diffDays > 0) out.push(`You're on track to reach "${goal.name}" ${diffDays} day(s) early.`);
        else if(diffDays < 0) out.push(`At current pace, "${goal.name}" may finish ${Math.abs(diffDays)} day(s) late.`);
      }
    }
    const cfg = Store.state.budgetConfig;
    const { start,end } = Budget.periodRange();
    const spent = Budget.spentInRange(start,end);
    if(spent > cfg.amount) out.push(`You exceeded your ${cfg.type} budget by ${Utils.fmtMoney(spent-cfg.amount)}.`);
    const highCat = Budget.highestCategory();
    if(highCat) out.push(`${highCat.category} is your top spending category at ${Utils.fmtMoney(highCat.total)}.`);
    if(!out.length) out.push('Add more expenses and goal contributions to unlock personalized insights.');
    return out;
  },

  render(){
    const el = document.getElementById('view-analytics');
    const saved = Dashboard.totalSavings();
    const spent = Budget.totalSpentAllTime();
    const netGain = saved - spent;
    const owedToYou = Store.state.debts.filter(d=>Debt.isOwedToYou(d)).reduce((s,d)=>s+Debt.currentOwed(d),0);
    const youOwe = Store.state.debts.filter(d=>!Debt.isOwedToYou(d)).reduce((s,d)=>s+Debt.currentOwed(d),0);
    const netDebtPosition = owedToYou-youOwe;
    const health = Budget.healthScore();
    const heat = this.heatmapData();
    let heatCells = '';
    const today = new Date();
    for(let i=181;i>=0;i--){
      const d = Utils.addDays(today,-i);
      const ds = Utils.dateStr(d);
      const level = Math.min(4, heat[ds]||0);
      heatCells += `<div class="heat-cell" data-level="${level}" title="${ds}"></div>`;
    }

    el.innerHTML = `
      <div class="section-head">
        <div><div class="section-title">Analytics</div><div class="section-sub">Full financial overview</div></div>
      </div>

      <div class="grid grid-4" style="margin-bottom:var(--gap);">
        <div class="card"><div class="card-label">Money Saved</div><div class="card-value">${Utils.fmtMoney(saved)}</div></div>
        <div class="card"><div class="card-label">Money Spent</div><div class="card-value">${Utils.fmtMoney(spent)}</div></div>
        <div class="card"><div class="card-label">Net Gain / Loss</div><div class="card-value ${netGain<0?'text-accent':''}">${Utils.fmtMoney(netGain)}</div></div>
        <div class="card"><div class="card-label">Net Debt Position</div><div class="card-value">${Utils.fmtMoney(netDebtPosition)}</div><div class="card-sub">${netDebtPosition>=0?'Net receivable':'Net payable'} · owed to you ${Utils.fmtMoney(owedToYou)} · you owe ${Utils.fmtMoney(youOwe)}</div></div>
      </div>

      <div class="grid grid-4" style="margin-bottom:var(--gap);">
        <div class="card"><div class="card-label">Savings Rate</div><div class="card-value">${this.savingsRate().toFixed(1)}%</div></div>
        <div class="card"><div class="card-label">Budget Accuracy</div><div class="card-value">${this.budgetAccuracy().toFixed(0)}%</div></div>
        <div class="card"><div class="card-label">Collection Rate</div><div class="card-value">${this.collectionRate().toFixed(0)}%</div></div>
        <div class="card"><div class="card-label">Financial Health Score</div><div class="card-value">${health}</div></div>
      </div>

      <div class="grid grid-4" style="margin-bottom:var(--gap);">
        <div class="card"><div class="card-label">Avg Weekly Savings</div><div class="card-value" style="font-size:18px;">${Utils.fmtMoney(Store.state.goals.reduce((s,g)=>s+Savings.averageContribution(g),0))}</div></div>
        <div class="card"><div class="card-label">Avg Monthly Spending</div><div class="card-value" style="font-size:18px;">${Utils.fmtMoney(Budget.averageDailySpending()*30)}</div></div>
        <div class="card"><div class="card-label">Savings Consistency</div><div class="card-value">${this.savingsConsistency().toFixed(0)}%</div></div>
        <div class="card"><div class="card-label">Longest Saving Streak</div><div class="card-value">${Savings.longestStreakAll(Store.state)}d</div></div>
      </div>

      <div class="grid grid-3" style="margin-bottom:var(--gap);">
        <div class="card"><div class="card-label">Projected Year-End Savings</div><div class="card-value" style="font-size:18px;">${Utils.fmtMoney(this.projectedYearEndSavings())}</div></div>
        <div class="card"><div class="card-label">Projected Debt Collection</div><div class="card-value" style="font-size:18px;">${Utils.fmtMoney(this.projectedDebtCollection())}</div></div>
        <div class="card"><div class="card-label">Projected Budget (period end)</div><div class="card-value" style="font-size:18px;">${Utils.fmtMoney(Budget.projectedEndOfPeriod())}</div></div>
      </div>

      <div class="card" style="margin-bottom:var(--gap);">
        <div class="card-label" style="margin-bottom:12px;">Contribution Heatmap — Last 6 Months</div>
        <div class="heatmap">${heatCells}</div>
      </div>

      <div class="grid grid-2" style="margin-bottom:var(--gap);">
        <div class="card">
          <div class="card-label" style="margin-bottom:12px;">Savings Growth Trend</div>
          <div id="analyticsArea"></div>
        </div>
        <div class="card">
          <div class="card-label" style="margin-bottom:12px;">Smart Insights</div>
          ${this.insights().map(t=>`<div class="insight-row">${Utils.escapeHtml(t)}</div>`).join('')}
        </div>
      </div>

    `;

    const labels = [], data = [];
    let running = 0;
    const sortedEntries = [];
    Store.state.goals.forEach(g => Object.entries(g.entries||{}).forEach(([date,e])=>{
      if(e.status==='completed'||e.status==='partial') sortedEntries.push({date, amount:e.amount});
    }));
    sortedEntries.sort((a,b)=>a.date.localeCompare(b.date));
    const byMonth = {};
    sortedEntries.forEach(e=>{ const m = e.date.slice(0,7); byMonth[m] = (byMonth[m]||0) + e.amount; });
    Object.keys(byMonth).sort().forEach(m=>{ running += byMonth[m]; labels.push(m); data.push(running); });
    if(!labels.length){ labels.push(Utils.dateStr(new Date()).slice(0,7)); data.push(saved); }
    Charts.line(document.getElementById('analyticsArea'), 'analyticsArea', labels, [{label:'Cumulative Savings', data}], {area:true});
  }
};

const Settings = {
  render(){
    const el = document.getElementById('view-settings');
    const s = Store.state.settings;
    el.innerHTML = `
      <div class="section-head"><div><div class="section-title">Settings</div><div class="section-sub">Preferences, data & currency</div></div></div>

      <div class="card" style="margin-bottom:var(--gap);">
        <div class="card-label" style="margin-bottom:12px;">Currency</div>
        <div class="chip-group currency-grid" id="currChips">
          ${[['₱','PHP'],['$','USD'],['€','EUR'],['¥','JPY'],['£','GBP'],['A$','AUD'],['C$','CAD'],['Fr','CHF'],['CN¥','CNY'],['₹','INR'],['₩','KRW'],['S$','SGD'],['HK$','HKD'],['NZ$','NZD'],['฿','THB'],['Rp','IDR'],['RM','MYR'],['₫','VND'],['R$','BRL'],['Mex$','MXN'],['R','ZAR']].map(([sym,name])=>`<button type="button" class="chip ${s.currency===sym?'selected':''}" data-c="${sym}">${sym} ${name}</button>`).join('')}
        </div>
      </div>

      <div class="card" style="margin-bottom:var(--gap);">
        <div class="card-label" style="margin-bottom:12px;">Data</div>
        <div class="btn-row">
          <button class="btn" id="exportBtn">EXPORT DATA</button>
          <button class="btn" id="importBtn">IMPORT DATA</button>
          <input type="file" id="importFile" accept="application/json" class="hidden">
          <button class="btn btn-danger" id="resetBtn">RESET ALL DATA</button>
        </div>
      </div>

    `;

    document.getElementById('currChips').querySelectorAll('.chip').forEach(c=>{
      c.addEventListener('click', ()=>{ Store.state.settings.currency = c.dataset.c; Core.refreshAllData(); });
    });
    document.getElementById('exportBtn').onclick = () => {
      const blob = new Blob([JSON.stringify(Store.state, null, 2)], {type:'application/json'});
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `budget-tracker-export-${Utils.todayStr()}.json`;
      a.click();
      Toast.show('Data exported.');
    };
    const fileInput = document.getElementById('importFile');
    document.getElementById('importBtn').onclick = () => fileInput.click();
    fileInput.onchange = (e) => {
      const file = e.target.files[0];
      if(!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        try{
          const data = JSON.parse(reader.result);
          Store.state = Object.assign(Store.defaults(), data);
          Core.refreshAllData();
          document.body.dataset.theme = Store.state.settings.theme;
          Toast.show('Data imported successfully.');
        }catch(err){ Toast.show('Invalid file format.', {warn:true}); }
      };
      reader.readAsText(file);
    };
    document.getElementById('resetBtn').onclick = () => {
      Modal.confirm('This will permanently erase all goals, expenses, and debt records. This cannot be undone.', ()=>{
        Store.state = Store.defaults();
        Core.refreshAllData();
        Toast.show('All data has been reset.');
      }, { danger:true, okLabel:'Reset Everything', title:'Reset All Data' });
    };
  }
};