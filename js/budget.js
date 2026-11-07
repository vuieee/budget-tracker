const PAYMENT_METHODS = ['Cash','GCash','Bank','Credit Card','Other'];

const Budget = {
  filters: { category:'all', method:'all', from:'', to:'' },

  periodRange(){
    const cfg = Store.state.budgetConfig;
    const now = new Date();
    if(cfg.type === 'weekly'){
      const start = Calendar.startOfWeek(now);
      return { start, end: Utils.addDays(start,6) };
    }
    if(cfg.type === 'yearly'){
      return { start:new Date(now.getFullYear(),0,1), end:new Date(now.getFullYear(),11,31) };
    }
    if(cfg.type === 'custom' && cfg.customStart && cfg.customEnd){
      return { start: Utils.parseDate(cfg.customStart), end: Utils.parseDate(cfg.customEnd) };
    }
    return { start:new Date(now.getFullYear(), now.getMonth(),1), end:new Date(now.getFullYear(), now.getMonth()+1,0) };
  },

  spentInRange(start,end){
    return Store.state.expenses
      .filter(e => { const d = Utils.parseDate(e.date); return d >= start && d <= end; })
      .reduce((s,e)=> s+e.amount, 0);
  },
  spentToday(){ const t = new Date(); return this.spentInRange(t,t); },
  spentThisWeek(){ const s = Calendar.startOfWeek(new Date()); return this.spentInRange(s, Utils.addDays(s,6)); },
  spentThisMonth(){ const n = new Date(); return this.spentInRange(new Date(n.getFullYear(),n.getMonth(),1), new Date(n.getFullYear(),n.getMonth()+1,0)); },
  spentThisYear(){ const n = new Date(); return this.spentInRange(new Date(n.getFullYear(),0,1), new Date(n.getFullYear(),11,31)); },

  remainingBudget(){
    const { start,end } = this.periodRange();
    return Store.state.budgetConfig.amount - this.spentInRange(start,end);
  },

  totalSpentAllTime(){ return Store.state.expenses.reduce((s,e)=>s+e.amount,0); },

  averageDailySpending(){
    const exp = Store.state.expenses;
    if(!exp.length) return 0;
    const dates = exp.map(e=>Utils.parseDate(e.date));
    const min = new Date(Math.min(...dates));
    const days = Math.max(1, Utils.daysBetween(min, new Date())+1);
    return this.totalSpentAllTime() / days;
  },
  averageWeeklySpending(){ return this.averageDailySpending() * 7; },

  dailyTotals(){
    const map = {};
    Store.state.expenses.forEach(e => { map[e.date] = (map[e.date]||0) + e.amount; });
    return map;
  },
  highestSpendingDay(){
    const map = this.dailyTotals();
    let best = null;
    Object.entries(map).forEach(([date,total])=>{ if(!best || total > best.total) best = {date,total}; });
    return best;
  },
  categoryTotals(){
    const map = {};
    Store.state.expenses.forEach(e => { map[e.category] = (map[e.category]||0) + e.amount; });
    return map;
  },
  highestCategory(){
    const map = this.categoryTotals();
    let best = null;
    Object.entries(map).forEach(([c,t])=>{ if(!best || t>best.total) best = {category:c,total:t}; });
    return best;
  },
  lowestCategory(){
    const map = this.categoryTotals();
    let low = null;
    Object.entries(map).forEach(([c,t])=>{ if(!low || t<low.total) low = {category:c,total:t}; });
    return low;
  },

  healthScore(){
    const { start,end } = this.periodRange();
    const spent = this.spentInRange(start,end);
    const budget = Store.state.budgetConfig.amount || 1;
    const ratio = spent/budget;
    let score = ratio <= 1 ? 100 - ratio*35 : Math.max(0, 65 - (ratio-1)*90);
    return Math.round(Utils.clamp(score,0,100));
  },

  burnRate(){
    const { start,end } = this.periodRange();
    const spent = this.spentInRange(start,end);
    const totalDays = Utils.daysBetween(start,end)+1;
    const elapsed = Utils.clamp(Utils.daysBetween(start,new Date())+1, 1, totalDays);
    const idealPace = (Store.state.budgetConfig.amount/totalDays) * elapsed;
    return { spent, idealPace, totalDays, elapsed };
  },

  projectedEndOfPeriod(){
    const { spent, totalDays, elapsed } = this.burnRate();
    return (spent/elapsed) * totalDays;
  },

  weeklySeries(){
    const labels = [], data = [];
    for(let i=6;i>=0;i--){
      const d = Utils.addDays(new Date(), -i);
      labels.push(d.toLocaleDateString(undefined,{weekday:'short'}));
      data.push(this.spentInRange(d,d));
    }
    return { labels, data };
  },

  monthlyTrend(){
    const labels = [], data = [];
    const now = new Date();
    for(let i=5;i>=0;i--){
      const d = new Date(now.getFullYear(), now.getMonth()-i, 1);
      labels.push(Utils.monthName(d.getMonth()).slice(0,3));
      data.push(this.spentInRange(d, new Date(d.getFullYear(), d.getMonth()+1,0)));
    }
    return { labels, data };
  },

  render(){
    const el = document.getElementById('view-budget');
    const cfg = Store.state.budgetConfig;
    const remaining = this.remainingBudget();
    const health = this.healthScore();
    const highDay = this.highestSpendingDay();
    const highCat = this.highestCategory();
    const lowCat = this.lowestCategory();
    const projected = this.projectedEndOfPeriod();

    el.innerHTML = `
      <div class="section-head">
        <div>
          <div class="section-title">Budget Tracker</div>
          <div class="section-sub">${cfg.type.toUpperCase()} BUDGET · ${Utils.fmtMoney(cfg.amount)}</div>
        </div>
        <div class="btn-row">
          <button class="btn" id="configBudgetBtn">CONFIGURE BUDGET</button>
          <button class="btn" id="manageCatBtn">CATEGORIES</button>
          <button class="btn btn-primary" id="addExpenseBtn">+ ADD EXPENSE</button>
        </div>
      </div>

      <div class="grid grid-4" style="margin-bottom:var(--gap);">
        <div class="card"><div class="card-label">Remaining Budget</div><div class="card-value">${Utils.fmtMoney(remaining)}</div><div class="card-sub ${remaining<0?'neg':'pos'}">${remaining<0?'over budget':'on track'}</div></div>
        <div class="card"><div class="card-label">Spent Today</div><div class="card-value">${Utils.fmtMoney(this.spentToday())}</div></div>
        <div class="card"><div class="card-label">Spent This Week</div><div class="card-value">${Utils.fmtMoney(this.spentThisWeek())}</div></div>
        <div class="card"><div class="card-label">Spent This Month</div><div class="card-value">${Utils.fmtMoney(this.spentThisMonth())}</div></div>
      </div>

      <div class="grid grid-4" style="margin-bottom:var(--gap);">
        <div class="card"><div class="card-label">Spent This Year</div><div class="card-value">${Utils.fmtMoney(this.spentThisYear())}</div></div>
        <div class="card"><div class="card-label">Avg Daily Spending</div><div class="card-value">${Utils.fmtMoney(this.averageDailySpending())}</div></div>
        <div class="card"><div class="card-label">Highest Spending Day</div><div class="card-value" style="font-size:16px;">${highDay?Utils.fmtMoney(highDay.total):'—'}</div><div class="card-sub">${highDay?Utils.fmtDateShort(highDay.date):'no data'}</div></div>
        <div class="card"><div class="card-label">Budget Health Score</div><div class="card-value">${health}</div><div class="progress-wrap" style="margin-top:8px;">${Utils.progressBar(health)}</div></div>
      </div>

      <div class="grid grid-2" style="margin-bottom:var(--gap);">
        <div class="card"><div class="card-label">Highest Category</div><div class="card-value" style="font-size:16px;">${highCat?highCat.category:'—'}</div><div class="card-sub">${highCat?Utils.fmtMoney(highCat.total):''}</div></div>
        <div class="card"><div class="card-label">Lowest Category</div><div class="card-value" style="font-size:16px;">${lowCat?lowCat.category:'—'}</div><div class="card-sub">${lowCat?Utils.fmtMoney(lowCat.total):''}</div></div>
      </div>

      <div class="card" style="margin-bottom:var(--gap);">
        <div class="card-label">Budget vs Actual — Projected End of Period</div>
        <div class="card-value">${Utils.fmtMoney(projected)}</div>
        <div class="card-sub ${projected>cfg.amount?'neg':'pos'}">${projected>cfg.amount ? `projected overspend of ${Utils.fmtMoney(projected-cfg.amount)}` : `projected underspend of ${Utils.fmtMoney(cfg.amount-projected)}`}</div>
      </div>

      <div class="grid grid-2" style="margin-bottom:var(--gap);">
        <div class="card"><div class="card-label" style="margin-bottom:12px;">Category Distribution</div><div id="pieChart"></div></div>
        <div class="card"><div class="card-label" style="margin-bottom:12px;">Weekly Spending</div><div id="barChart"></div></div>
      </div>
      <div class="grid grid-2" style="margin-bottom:var(--gap);">
        <div class="card"><div class="card-label" style="margin-bottom:12px;">Monthly Trend</div><div id="lineChart"></div></div>
        <div class="card"><div class="card-label" style="margin-bottom:12px;">Budget vs Actual (6mo)</div><div id="vsChart"></div></div>
      </div>

      <div class="card">
        <div class="flex-between" style="margin-bottom:14px;">
          <div class="card-label" style="margin-bottom:0;">Expenses</div>
        </div>
        <div class="filters-bar">
          <select id="filterCategory"><option value="all">All Categories</option>${Store.state.categories.map(c=>`<option value="${c}">${c}</option>`).join('')}</select>
          <select id="filterMethod"><option value="all">All Methods</option>${PAYMENT_METHODS.map(m=>`<option value="${m}">${m}</option>`).join('')}</select>
          <input type="date" id="filterFrom">
          <input type="date" id="filterTo">
        </div>
        <div class="table-scroll">
          <table>
            <thead><tr><th>Date</th><th>Title</th><th>Category</th><th>Method</th><th>Amount</th><th></th></tr></thead>
            <tbody id="expenseRows"></tbody>
          </table>
        </div>
      </div>
    `;

    document.getElementById('configBudgetBtn').onclick = () => this.openConfigModal();
    document.getElementById('manageCatBtn').onclick = () => this.openCategoryModal();
    document.getElementById('addExpenseBtn').onclick = () => this.openExpenseModal();

    ['filterCategory','filterMethod','filterFrom','filterTo'].forEach(id=>{
      document.getElementById(id).addEventListener('change', (e)=>{
        const map = { filterCategory:'category', filterMethod:'method', filterFrom:'from', filterTo:'to' };
        this.filters[map[id]] = e.target.value;
        this.renderExpenseRows();
      });
    });

    this.renderExpenseRows();

    const cat = this.categoryTotals();
    Charts.pie(document.getElementById('pieChart'), 'budgetPie', Object.keys(cat), Object.values(cat));
    const week = this.weeklySeries();
    Charts.bar(document.getElementById('barChart'), 'budgetBar', week.labels, week.data);
    const trend = this.monthlyTrend();
    Charts.line(document.getElementById('lineChart'), 'budgetLine', trend.labels, [{label:'Spending', data:trend.data}], {area:true});
    Charts.groupedBar(document.getElementById('vsChart'), 'budgetVs', trend.labels, [
      { label:'Budget', data: trend.labels.map(()=>cfg.amount) },
      { label:'Actual', data: trend.data }
    ]);
  },

  renderExpenseRows(){
    const tbody = document.getElementById('expenseRows');
    if(!tbody) return;
    let list = [...Store.state.expenses].sort((a,b)=> b.date.localeCompare(a.date));
    const f = this.filters;
    if(f.category !== 'all') list = list.filter(e=>e.category===f.category);
    if(f.method !== 'all') list = list.filter(e=>e.method===f.method);
    if(f.from) list = list.filter(e=>e.date >= f.from);
    if(f.to) list = list.filter(e=>e.date <= f.to);
    if(!list.length){ tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:var(--fg-faint); padding:24px;">NO EXPENSES LOGGED</td></tr>`; return; }
    tbody.innerHTML = list.map(e => `
      <tr>
        <td>${Utils.fmtDateShort(e.date)}</td>
        <td>${Utils.escapeHtml(e.title)}</td>
        <td>${Utils.escapeHtml(e.category)}</td>
        <td>${Utils.escapeHtml(e.method)}</td>
        <td>${Utils.fmtMoney(e.amount)}</td>
        <td class="lr-actions">
          <button class="btn btn-sm" data-edit="${e.id}">EDIT</button>
          <button class="btn btn-sm btn-danger" data-del="${e.id}">DEL</button>
        </td>
      </tr>
    `).join('');
    tbody.querySelectorAll('[data-edit]').forEach(b=> b.addEventListener('click', ()=> this.openExpenseModal(b.dataset.edit)));
    tbody.querySelectorAll('[data-del]').forEach(b=> b.addEventListener('click', ()=> this.deleteExpense(b.dataset.del)));
  },

  openExpenseModal(editId){
    const editing = editId ? Store.state.expenses.find(e=>e.id===editId) : null;
    const cats = Store.state.categories;
    Modal.open(editing ? 'Edit Expense' : 'Add Expense', `
      <div class="field"><label>Title</label><input id="eTitle" placeholder="Groceries" value="${editing?Utils.escapeHtml(editing.title):''}"></div>
      <div class="field-row">
        <div class="field"><label>Amount</label><input id="eAmount" type="number" min="0" step="0.01" value="${editing?editing.amount:''}"></div>
        <div class="field"><label>Date</label><input id="eDate" type="date" value="${editing?editing.date:Utils.todayStr()}"></div>
      </div>
      <div class="field"><label>Category</label>
        <select id="eCategory">${cats.map(c=>`<option value="${c}" ${editing&&editing.category===c?'selected':''}>${c}</option>`).join('')}</select>
      </div>
      <div class="field">
        <label>Payment Method</label>
        <div class="chip-group" id="methodChips2">
          ${PAYMENT_METHODS.map(m=>`<button type="button" class="chip ${editing&&editing.method===m?'selected':(!editing&&m==='Cash'?'selected':'')}" data-m="${m}">${m.toUpperCase()}</button>`).join('')}
        </div>
      </div>
      <div class="field"><label>Notes</label><textarea id="eNotes">${editing?editing.notes||'':''}</textarea></div>
      <div class="modal-foot">
        <button class="btn" id="eCancel">Cancel</button>
        <button class="btn btn-primary" id="eSave">${editing?'Save Changes':'Add Expense'}</button>
      </div>
    `);
    const chips = document.getElementById('methodChips2');
    chips.querySelectorAll('.chip').forEach(c=> c.addEventListener('click', ()=>{ chips.querySelectorAll('.chip').forEach(x=>x.classList.remove('selected')); c.classList.add('selected'); }));
    document.getElementById('eCancel').onclick = () => Modal.close();
    document.getElementById('eSave').onclick = () => {
      const title = document.getElementById('eTitle').value.trim();
      const amount = parseFloat(document.getElementById('eAmount').value);
      const date = document.getElementById('eDate').value;
      const category = document.getElementById('eCategory').value;
      const method = chips.querySelector('.chip.selected')?.dataset.m || 'Cash';
      const notes = document.getElementById('eNotes').value.trim();
      if(!title || !amount || !date){ Toast.show('Please fill in title, amount and date.', {warn:true}); return; }
      if(editing){
        Object.assign(editing, { title, amount, date, category, method, notes });
        Store.logActivity(`Updated expense "${title}"`, 'expense');
      } else {
        Store.state.expenses.push({ id: Utils.uid(), title, amount, date, category, method, notes });
        Store.logActivity(`Logged ${Utils.fmtMoney(amount)} — ${title}`, 'expense');
      }
      Modal.close();
      Core.refreshAllData();
    };
  },

  deleteExpense(id){
    const e = Store.state.expenses.find(x=>x.id===id);
    Store.state.deleted.push({ type:'expense', data:e, ts:Date.now() });
    Store.state.expenses = Store.state.expenses.filter(x=>x.id!==id);
    Store.logActivity(`Deleted expense "${e.title}"`, 'expense');
    Core.refreshAllData();
    Toast.show('Expense deleted.', { undo: () => { Store.state.expenses.push(e); Core.refreshAllData(); } });
  },

  openConfigModal(){
    const cfg = Store.state.budgetConfig;
    Modal.open('Configure Budget', `
      <div class="field">
        <label>Budget Type</label>
        <div class="chip-group" id="typeChips">
          ${['weekly','monthly','yearly','custom'].map(t=>`<button type="button" class="chip ${cfg.type===t?'selected':''}" data-t="${t}">${t.toUpperCase()}</button>`).join('')}
        </div>
      </div>
      <div class="field"><label>Budget Amount</label><input id="cfgAmount" type="number" min="0" step="0.01" value="${cfg.amount}"></div>
      <div class="field-row" id="customRange" style="display:${cfg.type==='custom'?'grid':'none'};">
        <div class="field"><label>Custom Start</label><input id="cfgStart" type="date" value="${cfg.customStart||''}"></div>
        <div class="field"><label>Custom End</label><input id="cfgEnd" type="date" value="${cfg.customEnd||''}"></div>
      </div>
      <div class="modal-foot">
        <button class="btn" id="cfgCancel">Cancel</button>
        <button class="btn btn-primary" id="cfgSave">Save</button>
      </div>
    `);
    const chips = document.getElementById('typeChips');
    chips.querySelectorAll('.chip').forEach(c=> c.addEventListener('click', ()=>{
      chips.querySelectorAll('.chip').forEach(x=>x.classList.remove('selected'));
      c.classList.add('selected');
      document.getElementById('customRange').style.display = c.dataset.t==='custom' ? 'grid' : 'none';
    }));
    document.getElementById('cfgCancel').onclick = () => Modal.close();
    document.getElementById('cfgSave').onclick = () => {
      const type = chips.querySelector('.chip.selected')?.dataset.t || 'monthly';
      const amount = parseFloat(document.getElementById('cfgAmount').value) || 0;
      Store.state.budgetConfig = { type, amount, customStart: document.getElementById('cfgStart').value, customEnd: document.getElementById('cfgEnd').value };
      Store.logActivity(`Set ${type} budget to ${Utils.fmtMoney(amount)}`, 'budget');
      Modal.close();
      Core.refreshAllData();
    };
  },

  openCategoryModal(){
    const render = () => `
      <div class="field"><label>Add Category</label>
        <div style="display:flex; gap:8px;">
          <input id="newCatInput" placeholder="e.g. Pets" style="flex:1;">
          <button class="btn btn-primary btn-sm" id="addCatBtn">ADD</button>
        </div>
      </div>
      <div class="list" id="catList">
        ${Store.state.categories.map(c=>`
          <div class="list-row">
            <span>${Utils.escapeHtml(c)}</span>
            <button class="btn btn-sm btn-danger" data-cat="${Utils.escapeHtml(c)}">REMOVE</button>
          </div>`).join('')}
      </div>
    `;
    Modal.open('Manage Categories', render());
    const bind = () => {
      document.getElementById('addCatBtn').onclick = () => {
        const val = document.getElementById('newCatInput').value.trim();
        if(!val) return;
        if(Store.state.categories.includes(val)){ Toast.show('Category already exists.', {warn:true}); return; }
        Store.state.categories.push(val);
        Store.save();
        Modal.open('Manage Categories', render());
        bind();
        this.render();
      };
      document.querySelectorAll('[data-cat]').forEach(b=>{
        b.onclick = () => {
          Store.state.categories = Store.state.categories.filter(c=>c!==b.dataset.cat);
          Store.save();
          Modal.open('Manage Categories', render());
          bind();
          this.render();
        };
      });
    };
    bind();
  }
};