const Savings = {
  selectedGoalId: null,

  periodDays(method, customDays){
    if(method==='daily') return 1;
    if(method==='weekly') return 7;
    if(method==='biweekly') return 14;
    if(method==='monthly') return 30;
    return customDays || 7;
  },

  savedAmount(goal){
    return Object.values(goal.entries||{}).reduce((sum,e)=> sum + ((e.status==='completed'||e.status==='partial') ? (e.amount||0) : 0), 0);
  },
  remainingAmount(goal){ return Math.max(0, goal.target - this.savedAmount(goal)); },
  progressPct(goal){ return goal.target > 0 ? Utils.clamp((this.savedAmount(goal)/goal.target)*100, 0, 999) : 0; },
  remainingDays(goal){ return Math.max(0, Utils.daysBetween(new Date(), Utils.parseDate(goal.targetDate))); },
  totalPeriods(goal){
    const total = Utils.daysBetween(Utils.parseDate(goal.startDate), Utils.parseDate(goal.targetDate));
    return Math.max(1, Math.ceil(total / this.periodDays(goal.method, goal.customDays)));
  },
  remainingPeriods(goal){
    const total = this.remainingDays(goal);
    return Math.max(1, Math.ceil(total / this.periodDays(goal.method, goal.customDays)));
  },
  requiredPerPeriod(goal){
    return this.remainingAmount(goal) / this.remainingPeriods(goal);
  },
  contributionEntries(goal){
    return Object.entries(goal.entries||{})
      .filter(([,e]) => e.status==='completed' || e.status==='partial')
      .sort((a,b)=> a[0].localeCompare(b[0]));
  },
  averageContribution(goal){
    const list = this.contributionEntries(goal);
    if(!list.length) return 0;
    return list.reduce((s,[,e])=>s+(e.amount||0),0) / list.length;
  },
  elapsedPeriods(goal){
    const elapsed = Utils.daysBetween(Utils.parseDate(goal.startDate), new Date());
    return Math.max(1, Math.floor(Math.max(0,elapsed) / this.periodDays(goal.method, goal.customDays)) + 1);
  },
  successRate(goal){
    const contributed = this.contributionEntries(goal).length;
    return Utils.clamp(contributed / this.elapsedPeriods(goal), 0, 1) || 0.0001;
  },
  estimatedCompletion(goal){
    const avg = this.averageContribution(goal) || (goal.target / this.totalPeriods(goal));
    const remaining = this.remainingAmount(goal);
    if(avg <= 0) return null;
    const periodsNeeded = Math.ceil(remaining/avg);
    return Utils.addDays(new Date(), periodsNeeded * this.periodDays(goal.method, goal.customDays));
  },
  projectedIfMisses(goal){
    const rate = this.successRate(goal);
    const base = this.estimatedCompletion(goal);
    if(!base) return null;
    const baseDays = Utils.daysBetween(new Date(), base);
    return Utils.addDays(new Date(), Math.ceil(baseDays / rate));
  },
  currentStreak(goal){
    let streak = 0;
    let d = new Date();
    while(true){
      const ds = Utils.dateStr(d);
      const e = goal.entries && goal.entries[ds];
      if(e && (e.status==='completed' || e.status==='partial')){ streak++; d = Utils.addDays(d,-1); }
      else if(ds === Utils.todayStr()){ d = Utils.addDays(d,-1); continue; }
      else break;
    }
    return streak;
  },
  longestStreak(goal){
    const dates = Object.keys(goal.entries||{}).filter(ds => {
      const e = goal.entries[ds];
      return e.status==='completed' || e.status==='partial';
    }).sort();
    if(!dates.length) return 0;
    let longest = 1, run = 1;
    for(let i=1;i<dates.length;i++){
      const prev = Utils.parseDate(dates[i-1]);
      const cur = Utils.parseDate(dates[i]);
      if(Utils.daysBetween(prev,cur) === 1) run++; else run = 1;
      longest = Math.max(longest, run);
    }
    return longest;
  },
  longestStreakAll(state){
    return Math.max(0, ...state.goals.map(g=>this.longestStreak(g)));
  },

  render(){
    const el = document.getElementById('view-savings');
    if(this.selectedGoalId && Store.state.goals.find(g=>g.id===this.selectedGoalId)){
      this.renderDetail(el, this.selectedGoalId);
    } else {
      this.selectedGoalId = null;
      this.renderList(el);
    }
  },

  renderList(el){
    const goals = Store.state.goals;
    el.innerHTML = `
      <div class="section-head">
        <div>
          <div class="section-title">Savings Goals</div>
          <div class="section-sub">${goals.length} active goal${goals.length===1?'':'s'}</div>
        </div>
        <button class="btn btn-primary" id="newGoalBtn">+ NEW GOAL</button>
      </div>
      ${goals.length ? `<div class="grid grid-3" id="goalsGrid"></div>` : `
        <div class="empty-state">
          <p>No savings goals yet. Create one to start tracking contributions on the calendar.</p>
          <button class="btn btn-primary" id="newGoalBtn2">+ CREATE FIRST GOAL</button>
        </div>`}
    `;
    document.getElementById('newGoalBtn').onclick = () => this.openGoalModal();
    const btn2 = document.getElementById('newGoalBtn2');
    if(btn2) btn2.onclick = () => this.openGoalModal();

    const grid = document.getElementById('goalsGrid');
    if(grid){
      grid.innerHTML = goals.map(g => {
        const pct = this.progressPct(g);
        const daysLeft = this.remainingDays(g);
        return `
        <div class="card goal-card" data-id="${g.id}" style="cursor:pointer;">
          <div class="flex-between" style="margin-bottom:10px;">
            <div class="card-label">${Utils.escapeHtml(g.name)}</div>
            <span class="badge ${pct>=100?'ok':''}">${pct>=100?'DONE':g.method.toUpperCase()}</span>
          </div>
          <div class="card-value">${Utils.fmtMoney(this.savedAmount(g))}</div>
          <div class="card-sub">of ${Utils.fmtMoney(g.target)} target</div>
          <div class="progress-wrap" style="margin-top:14px;">
            ${Utils.progressBar(pct)}
            <div class="progress-meta"><span>${daysLeft} days left</span><span>${Utils.fmtDateShort(g.targetDate)}</span></div>
          </div>
        </div>`;
      }).join('');
      grid.querySelectorAll('.goal-card').forEach(card=>{
        card.addEventListener('click', ()=>{ this.selectedGoalId = card.dataset.id; this.render(); });
      });
    }
  },

  renderDetail(el, id){
    const g = Store.state.goals.find(x=>x.id===id);
    const pct = this.progressPct(g);
    const est = this.estimatedCompletion(g);
    const proj = this.projectedIfMisses(g);
    el.innerHTML = `
      <button class="btn btn-sm" id="backToGoals" style="margin-bottom:16px;">&lt; ALL GOALS</button>
      <div class="section-head">
        <div>
          <div class="section-title">${Utils.escapeHtml(g.name)}</div>
          <div class="section-sub">${Utils.fmtDateHuman(g.startDate)} &rarr; ${Utils.fmtDateHuman(g.targetDate)} · ${g.method.toUpperCase()}</div>
        </div>
        <div class="btn-row">
          <button class="btn" id="editGoalBtn">EDIT</button>
          <button class="btn btn-danger" id="deleteGoalBtn">DELETE</button>
        </div>
      </div>

      <div class="grid grid-4" style="margin-bottom:var(--gap);">
        <div class="card"><div class="card-label">Saved</div><div class="card-value">${Utils.fmtMoney(this.savedAmount(g))}</div><div class="card-sub">${pct.toFixed(1)}% complete</div></div>
        <div class="card"><div class="card-label">Remaining</div><div class="card-value">${Utils.fmtMoney(this.remainingAmount(g))}</div><div class="card-sub">${this.remainingDays(g)} days left</div></div>
        <div class="card"><div class="card-label">Required / period</div><div class="card-value">${Utils.fmtMoney(this.requiredPerPeriod(g))}</div><div class="card-sub">${g.method}</div></div>
        <div class="card"><div class="card-label">Est. completion</div><div class="card-value" style="font-size:16px;">${est ? Utils.fmtDateShort(est) : '—'}</div><div class="card-sub">if misses continue: ${proj ? Utils.fmtDateShort(proj) : '—'}</div></div>
      </div>

      <div class="grid grid-4" style="margin-bottom:var(--gap);">
        <div class="card"><div class="card-label">Current Streak</div><div class="card-value">${this.currentStreak(g)}d</div></div>
        <div class="card"><div class="card-label">Longest Streak</div><div class="card-value">${this.longestStreak(g)}d</div></div>
        <div class="card"><div class="card-label">Avg Contribution</div><div class="card-value">${Utils.fmtMoney(this.averageContribution(g))}</div></div>
        <div class="card"><div class="card-label">Progress</div><div class="progress-wrap" style="margin-top:6px;">${Utils.progressBar(pct)}</div></div>
      </div>

      <div class="card" id="goalCalendarCard">
        <div class="section-title" style="font-size:14px; margin-bottom:14px;">Contribution Calendar</div>
        <div id="goalCalendar"></div>
      </div>
    `;

    document.getElementById('backToGoals').onclick = () => { this.selectedGoalId = null; this.render(); };
    document.getElementById('editGoalBtn').onclick = () => this.openGoalModal(g.id);
    document.getElementById('deleteGoalBtn').onclick = () => this.deleteGoal(g.id);

    Calendar.state.cursor = new Date();
    Calendar.render(document.getElementById('goalCalendar'), {
      getDayInfo: (dateStr) => g.entries ? g.entries[dateStr] : null,
      remainingAt: () => this.remainingAmount(g),
      onDayClick: (dateStr) => this.openDayModal(g.id, dateStr)
    });
  },

  openGoalModal(editId){
    const editing = editId ? Store.state.goals.find(g=>g.id===editId) : null;
    const today = Utils.todayStr();
    Modal.open(editing ? 'Edit Savings Goal' : 'New Savings Goal', `
      <div class="field"><label>Goal Name</label><input id="gName" placeholder="Nintendo Switch 2" value="${editing ? Utils.escapeHtml(editing.name) : ''}"></div>
      <div class="field"><label>Target Amount</label><input id="gTarget" type="number" min="0" step="0.01" placeholder="30000" value="${editing ? editing.target : ''}"></div>
      <div class="field-row">
        <div class="field"><label>Start Date</label><input id="gStart" type="date" value="${editing ? editing.startDate : today}"></div>
        <div class="field"><label>Target Date</label><input id="gEnd" type="date" value="${editing ? editing.targetDate : ''}"></div>
      </div>
      <div class="field">
        <label>Saving Method</label>
        <div class="chip-group" id="methodChips">
          ${['daily','weekly','biweekly','monthly','custom'].map(m=>`<button type="button" class="chip ${editing && editing.method===m ? 'selected':(!editing && m==='weekly'?'selected':'')}" data-m="${m}">${m.toUpperCase()}</button>`).join('')}
        </div>
      </div>
      <div class="field" id="customDaysField" style="display:${editing && editing.method==='custom' ? 'flex':'none'};">
        <label>Custom Interval (days)</label><input id="gCustomDays" type="number" min="1" value="${editing ? (editing.customDays||7) : 7}">
      </div>
      <div class="modal-foot">
        <button class="btn" id="gCancel">Cancel</button>
        <button class="btn btn-primary" id="gSave">${editing?'Save Changes':'Create Goal'}</button>
      </div>
    `);
    const chips = document.getElementById('methodChips');
    chips.querySelectorAll('.chip').forEach(c=>{
      c.addEventListener('click', ()=>{
        chips.querySelectorAll('.chip').forEach(x=>x.classList.remove('selected'));
        c.classList.add('selected');
        document.getElementById('customDaysField').style.display = c.dataset.m==='custom' ? 'flex' : 'none';
      });
    });
    document.getElementById('gCancel').onclick = () => Modal.close();
    document.getElementById('gSave').onclick = () => {
      const name = document.getElementById('gName').value.trim();
      const target = parseFloat(document.getElementById('gTarget').value);
      const startDate = document.getElementById('gStart').value;
      const targetDate = document.getElementById('gEnd').value;
      const method = chips.querySelector('.chip.selected')?.dataset.m || 'weekly';
      const customDays = parseInt(document.getElementById('gCustomDays').value,10) || 7;
      if(!name || !target || !startDate || !targetDate){ Toast.show('Please fill in all required fields.', {warn:true}); return; }
      if(editing){
        Object.assign(editing, { name, target, startDate, targetDate, method, customDays });
        Store.logActivity(`Updated goal "${name}"`, 'goal');
        Toast.show('Goal updated.');
      } else {
        const goal = { id: Utils.uid(), name, target, startDate, targetDate, method, customDays, entries:{}, createdAt: Date.now() };
        Store.state.goals.push(goal);
        this.selectedGoalId = goal.id;
        Store.logActivity(`Created goal "${name}" (${Utils.fmtMoney(target)})`, 'goal');
        Toast.show('Goal created.');
      }
      Modal.close();
      Core.refreshAllData();
    };
  },

  deleteGoal(id){
    const g = Store.state.goals.find(x=>x.id===id);
    Modal.confirm(`Delete "${g.name}"? This removes all contribution history for this goal.`, ()=>{
      Store.state.deleted.push({ type:'goal', data:g, ts:Date.now() });
      Store.state.goals = Store.state.goals.filter(x=>x.id!==id);
      this.selectedGoalId = null;
      Store.logActivity(`Deleted goal "${g.name}"`, 'goal');
      Core.refreshAllData();
      Toast.show('Goal deleted.', { undo: () => {
        Store.state.goals.push(g);
        Core.refreshAllData();
      }});
    }, { danger:true, okLabel:'Delete' });
  },

  openDayModal(goalId, dateStr){
    const g = Store.state.goals.find(x=>x.id===goalId);
    const existing = (g.entries && g.entries[dateStr]) || {};
    Modal.open(Utils.fmtDateHuman(dateStr), `
      <div class="field"><label>Amount Saved</label><input id="dAmount" type="number" min="0" step="0.01" value="${existing.amount||''}"></div>
      <div class="field"><label>Notes</label><textarea id="dNotes" placeholder="Optional note...">${existing.notes||''}</textarea></div>
      <div class="field">
        <label>Status</label>
        <div class="chip-group" id="statusChips">
          ${[['completed','COMPLETED'],['partial','PARTIAL'],['missed','MISSED'],['skip','SKIP']].map(([v,l])=>
            `<button type="button" class="chip ${existing.status===v?'selected':''}" data-s="${v}">${l}</button>`).join('')}
        </div>
      </div>
      <div class="modal-foot">
        ${existing.status ? '<button class="btn btn-danger" id="dRemove">REMOVE ENTRY</button>' : ''}
        <button class="btn" id="dCancel">Cancel</button>
        <button class="btn btn-primary" id="dSave">Save</button>
      </div>
    `);
    const chips = document.getElementById('statusChips');
    chips.querySelectorAll('.chip').forEach(c=>{
      c.addEventListener('click', ()=>{ chips.querySelectorAll('.chip').forEach(x=>x.classList.remove('selected')); c.classList.add('selected'); });
    });
    document.getElementById('dCancel').onclick = () => Modal.close();
    const rm = document.getElementById('dRemove');
    if(rm) rm.onclick = () => {
      delete g.entries[dateStr];
      Store.logActivity(`Removed entry on ${Utils.fmtDateShort(dateStr)} for "${g.name}"`, 'goal');
      Modal.close();
      Core.refreshAllData();
    };
    document.getElementById('dSave').onclick = () => {
      const amount = parseFloat(document.getElementById('dAmount').value) || 0;
      const notes = document.getElementById('dNotes').value.trim();
      const status = chips.querySelector('.chip.selected')?.dataset.s || 'completed';
      if(!g.entries) g.entries = {};
      g.entries[dateStr] = { amount, notes, status };
      Store.logActivity(`${status==='completed'?'Saved':'Logged'} ${Utils.fmtMoney(amount)} for "${g.name}" on ${Utils.fmtDateShort(dateStr)}`, 'goal');
      Modal.close();
      Core.refreshAllData();
    };
  },

  openQuickContribution(){
    if(!Store.state.goals.length){ Toast.show('Create a savings goal first.', {warn:true}); return; }
    const options = Store.state.goals.map(g=>`<option value="${g.id}">${Utils.escapeHtml(g.name)}</option>`).join('');
    Modal.open('Quick Contribution', `
      <div class="field"><label>Goal</label><select id="qGoal">${options}</select></div>
      <div class="field"><label>Amount</label><input id="qAmount" type="number" min="0" step="0.01"></div>
      <div class="modal-foot">
        <button class="btn" id="qCancel">Cancel</button>
        <button class="btn btn-primary" id="qSave">Add</button>
      </div>
    `);
    document.getElementById('qCancel').onclick = () => Modal.close();
    document.getElementById('qSave').onclick = () => {
      const gid = document.getElementById('qGoal').value;
      const amount = parseFloat(document.getElementById('qAmount').value) || 0;
      const g = Store.state.goals.find(x=>x.id===gid);
      if(!amount){ Toast.show('Enter an amount.', {warn:true}); return; }
      if(!g.entries) g.entries = {};
      const today = Utils.todayStr();
      const prev = g.entries[today];
      g.entries[today] = { amount: (prev?prev.amount:0)+amount, notes: prev?prev.notes:'', status:'completed' };
      Store.logActivity(`Contributed ${Utils.fmtMoney(amount)} to "${g.name}"`, 'goal');
      Modal.close();
      Core.refreshAllData();
    };
  }
};