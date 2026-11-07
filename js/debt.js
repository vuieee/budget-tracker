const Debt = {
  freqDays(freq){
    return { daily:1, weekly:7, monthly:30, yearly:365 }[freq] || 30;
  },

  periodsElapsed(debt, toDate){
    const days = Math.max(0, Utils.daysBetween(Utils.parseDate(debt.dateBorrowed), toDate));
    return days / this.freqDays(debt.interestFreq);
  },

  interestAccumulated(debt, toDate = new Date()){
    if(debt.interestType === 'none' || !debt.rate) return 0;

    const periods = this.periodsElapsed(debt, toDate);
    const r = (debt.rate||0)/100;
    if(debt.interestType === 'compound'){
      return debt.amount * (Math.pow(1+r, periods) - 1);
    }
    return debt.amount * r * periods;
  },

  totalPaid(debt){
    return (debt.payments||[]).reduce((s,p)=>s+p.amount,0);
  },

  currentOwed(debt){
    if(debt.status === 'paid') return 0;
    const owed = debt.amount + this.interestAccumulated(debt) - this.totalPaid(debt);
    return Math.max(0, owed);
  },

  totalCollectable(debt){
    return debt.amount + this.interestAccumulated(debt);
  },

  isOwedToYou(debt){
    return debt.direction !== 'i-owe';
  },

  daysOverdue(debt){
    if(debt.status === 'paid') return 0;
    const days = Utils.daysBetween(Utils.parseDate(debt.dueDate), new Date());
    return days > 0 ? days : 0;
  },

  expectedCollectionDate(debt){ return debt.dueDate; },

  progressPct(debt){
    const total = this.totalCollectable(debt) || 1;
    return Utils.clamp((this.totalPaid(debt)/total)*100, 0, 100);
  },

  effectiveStatus(debt){
    if(debt.status === 'paid') return 'paid';
    if(this.daysOverdue(debt) > 0) return 'overdue';
    return 'active';
  },

  render(){
    const el = document.getElementById('view-debt');
    const debts = Store.state.debts;
    const owedToYou = debts.filter(d=>this.isOwedToYou(d)).reduce((s,d)=>s+this.currentOwed(d),0);
    const youOwe = debts.filter(d=>!this.isOwedToYou(d)).reduce((s,d)=>s+this.currentOwed(d),0);
    const overdueCount = debts.filter(d=>this.effectiveStatus(d)==='overdue').length;
    const totalReceived = debts.filter(d=>this.isOwedToYou(d)).reduce((s,d)=>s+this.totalPaid(d),0);

    el.innerHTML = `
      <div class="section-head">
        <div>
          <div class="section-title">Debt Tracker</div>
          <div class="section-sub">${debts.length} entr${debts.length===1?'y':'ies'} · ${overdueCount} overdue</div>
        </div>
        <button class="btn btn-primary" id="newDebtBtn">+ NEW ENTRY</button>
      </div>

      <div class="grid grid-3" style="margin-bottom:var(--gap);">
        <div class="card"><div class="card-label">Owed to You</div><div class="card-value">${Utils.fmtMoney(owedToYou)}</div><div class="card-sub">Includes money others owe you</div></div>
        <div class="card"><div class="card-label">You Owe</div><div class="card-value">${Utils.fmtMoney(youOwe)}</div><div class="card-sub">Money you owe others</div></div>
        <div class="card"><div class="card-label">Total Received</div><div class="card-value">${Utils.fmtMoney(totalReceived)}</div></div>
      </div>

      ${debts.length ? `<div class="grid grid-2" id="debtGrid"></div>` : `
        <div class="empty-state">
          <p>No entries tracked yet. Add money you owe or money someone owes you.</p>
          <button class="btn btn-primary" id="newDebtBtn2">+ ADD FIRST ENTRY</button>
        </div>`}
    `;
    document.getElementById('newDebtBtn').onclick = () => this.openDebtModal();
    const b2 = document.getElementById('newDebtBtn2');
    if(b2) b2.onclick = () => this.openDebtModal();

    const grid = document.getElementById('debtGrid');
    if(grid){
      grid.innerHTML = debts.map(d => {
        const status = this.effectiveStatus(d);
        const owed = this.currentOwed(d);
        const pct = this.progressPct(d);
        const receivable = this.isOwedToYou(d);
        return `
        <div class="card">
          <div class="flex-between" style="margin-bottom:10px;">
            <div>
              <div class="card-value" style="font-size:17px;">${receivable ? `${Utils.escapeHtml(d.borrower)} owes you` : `You owe ${Utils.escapeHtml(d.borrower)}`}</div>
              <div class="card-sub">${Utils.escapeHtml(d.phone||'')}</div>
            </div>
            <span class="badge ${status==='paid'?'ok':status==='overdue'?'warn':''}">${status.toUpperCase()}</span>
          </div>
          <div class="grid grid-2" style="gap:10px; margin-bottom:12px;">
            <div><div class="card-label">${receivable?'Owed to You':'You Owe'}</div><div class="card-value" style="font-size:18px;">${Utils.fmtMoney(owed)}</div></div>
            <div><div class="card-label">Interest Accrued</div><div class="card-value" style="font-size:18px;">${Utils.fmtMoney(this.interestAccumulated(d))}</div></div>
          </div>
          <div class="progress-wrap" style="margin-bottom:12px;">
            ${Utils.progressBar(pct)}
            <div class="progress-meta"><span>${receivable?'Received':'Paid'} ${Utils.fmtMoney(this.totalPaid(d))}</span><span>Due ${Utils.fmtDateShort(d.dueDate)}</span></div>
          </div>
          ${status==='overdue' ? `<div class="card-sub neg" style="margin-bottom:10px;">${this.daysOverdue(d)} days overdue</div>` : ''}
          <div class="btn-row">
            <button class="btn btn-sm" data-pay="${d.id}">${receivable?'+ RECEIVED':'+ PAYMENT'}</button>
            <button class="btn btn-sm" data-timeline="${d.id}">TIMELINE</button>
            <button class="btn btn-sm" data-edit="${d.id}">EDIT</button>
            <button class="btn btn-sm btn-danger" data-del="${d.id}">DELETE</button>
          </div>
        </div>`;
      }).join('');
      grid.querySelectorAll('[data-pay]').forEach(b=> b.addEventListener('click', ()=> this.openPaymentModal(b.dataset.pay)));
      grid.querySelectorAll('[data-timeline]').forEach(b=> b.addEventListener('click', ()=> this.openTimelineModal(b.dataset.timeline)));
      grid.querySelectorAll('[data-edit]').forEach(b=> b.addEventListener('click', ()=> this.openDebtModal(b.dataset.edit)));
      grid.querySelectorAll('[data-del]').forEach(b=> b.addEventListener('click', ()=> this.deleteDebt(b.dataset.del)));
    }
  },

  openDebtModal(editId){
    const editing = editId ? Store.state.debts.find(d=>d.id===editId) : null;
    Modal.open(editing ? 'Edit Debt Entry' : 'New Debt Entry', `
      <div class="field"><label>Who owes whom?</label>
        <select id="dDirection">
          <option value="owed-to-me" ${!editing||this.isOwedToYou(editing)?'selected':''}>They owe me</option>
          <option value="i-owe" ${editing&&!this.isOwedToYou(editing)?'selected':''}>I owe them</option>
        </select>
      </div>
      <div class="field"><label>Other Person</label><input id="dBorrower" value="${editing?Utils.escapeHtml(editing.borrower):''}"></div>
      <div class="field-row">
        <div class="field"><label>Starting Amount</label><input id="dAmount" type="number" min="0" step="0.01" value="${editing?editing.amount:''}"></div>
        <div class="field"><label>Start Date</label><input id="dDateBorrowed" type="date" value="${editing?editing.dateBorrowed:Utils.todayStr()}"></div>
      </div>
      <div class="field-row">
        <div class="field"><label>Interest Rate (%)</label><input id="dRate" type="number" min="0" step="0.01" value="${editing?editing.rate:0}"></div>
        <div class="field"><label>Payment Due Date</label><input id="dDue" type="date" value="${editing?editing.dueDate:''}"></div>
      </div>
      <div class="field">
        <label>Interest Type</label>
        <div class="chip-group" id="typeChipsD">
          ${['none','simple','compound'].map(t=>`<button type="button" class="chip ${editing&&editing.interestType===t?'selected':(!editing&&t==='none'?'selected':'')}" data-t="${t}">${t.toUpperCase()}</button>`).join('')}
        </div>
      </div>
      <div class="field">
        <label>Interest Frequency</label>
        <div class="chip-group" id="freqChipsD">
          ${['daily','weekly','monthly','yearly'].map(f=>`<button type="button" class="chip ${editing&&editing.interestFreq===f?'selected':(!editing&&f==='monthly'?'selected':'')}" data-f="${f}">${f.toUpperCase()}</button>`).join('')}
        </div>
      </div>
      <div class="field-row">
        <div class="field"><label>Phone Number</label><input id="dPhone" value="${editing?Utils.escapeHtml(editing.phone||''):''}"></div>
        <div class="field"><label>Status</label>
          <select id="dStatus">
            <option value="active" ${editing&&editing.status==='active'?'selected':''}>Active</option>
            <option value="paid" ${editing&&editing.status==='paid'?'selected':''}>Paid</option>
            <option value="overdue" ${editing&&editing.status==='overdue'?'selected':''}>Overdue</option>
          </select>
        </div>
      </div>
      <div class="field"><label>Notes</label><textarea id="dNotes">${editing?editing.notes||'':''}</textarea></div>
      <div class="modal-foot">
        <button class="btn" id="dCancel">Cancel</button>
        <button class="btn btn-primary" id="dSaveBtn">${editing?'Save Changes':'Create Entry'}</button>
      </div>
    `);
    const bindChips = (id) => {
      const c = document.getElementById(id);
      c.querySelectorAll('.chip').forEach(x=> x.addEventListener('click', ()=>{ c.querySelectorAll('.chip').forEach(y=>y.classList.remove('selected')); x.classList.add('selected'); }));
    };
    bindChips('typeChipsD'); bindChips('freqChipsD');
    document.getElementById('dCancel').onclick = () => Modal.close();
    document.getElementById('dSaveBtn').onclick = () => {
      const borrower = document.getElementById('dBorrower').value.trim();
      const direction = document.getElementById('dDirection').value;
      const amount = parseFloat(document.getElementById('dAmount').value);
      const dateBorrowed = document.getElementById('dDateBorrowed').value;
      const rate = parseFloat(document.getElementById('dRate').value) || 0;
      const dueDate = document.getElementById('dDue').value;
      const interestType = document.getElementById('typeChipsD').querySelector('.chip.selected')?.dataset.t || 'none';
      const interestFreq = document.getElementById('freqChipsD').querySelector('.chip.selected')?.dataset.f || 'monthly';
      const phone = document.getElementById('dPhone').value.trim();
      const status = document.getElementById('dStatus').value;
      const notes = document.getElementById('dNotes').value.trim();
      if(!borrower || !amount || !dateBorrowed || !dueDate){ Toast.show('Please fill in all required fields.', {warn:true}); return; }
      if(editing){
        Object.assign(editing, { borrower, direction, amount, dateBorrowed, rate, dueDate, interestType, interestFreq, phone, status, notes });
        Store.logActivity(`Updated debt entry for ${borrower}`, 'debt');
      } else {
        Store.state.debts.push({ id: Utils.uid(), borrower, direction, amount, dateBorrowed, rate, dueDate, interestType, interestFreq, phone, status, notes, payments:[] });
        Store.logActivity(`Added ${direction==='i-owe'?'debt owed to':'debt owed by'} ${borrower} (${Utils.fmtMoney(amount)})`, 'debt');
      }
      Modal.close();
      Core.refreshAllData();
    };
  },

  openPaymentModal(id){
    const d = Store.state.debts.find(x=>x.id===id);
    const receivable = this.isOwedToYou(d);
    Modal.open(`Record Payment — ${Utils.escapeHtml(d.borrower)}`, `
      <div class="card-sub" style="margin-bottom:14px;">${receivable?'They owe you':'You owe them'}: <strong>${Utils.fmtMoney(this.currentOwed(d))}</strong></div>
      <div class="field-row">
        <div class="field"><label>Amount</label><input id="pAmount" type="number" min="0" step="0.01"></div>
        <div class="field"><label>Date</label><input id="pDate" type="date" value="${Utils.todayStr()}"></div>
      </div>
      <div class="field"><label>Notes</label><textarea id="pNotes"></textarea></div>
      <div class="modal-foot">
        <button class="btn" id="pCancel">Cancel</button>
        <button class="btn btn-primary" id="pSave">${receivable?'Record Received Payment':'Record Payment'}</button>
      </div>
    `);
    document.getElementById('pCancel').onclick = () => Modal.close();
    document.getElementById('pSave').onclick = () => {
      const amount = parseFloat(document.getElementById('pAmount').value);
      const date = document.getElementById('pDate').value;
      const notes = document.getElementById('pNotes').value.trim();
      if(!amount || !date){ Toast.show('Enter an amount and date.', {warn:true}); return; }
      if(!d.payments) d.payments = [];
      d.payments.push({ id: Utils.uid(), amount, date, notes });
      if(this.currentOwed(d) <= 0.5) d.status = 'paid';
      Store.logActivity(`${receivable?'Received payment from':'Paid'} ${d.borrower}: ${Utils.fmtMoney(amount)}`, 'debt');
      Modal.close();
      Core.refreshAllData();
    };
  },

  openTimelineModal(id){
    const d = Store.state.debts.find(x=>x.id===id);
    const events = [
      { date:d.dateBorrowed, label:`${this.isOwedToYou(d)?'Lent':'Borrowed'} ${Utils.fmtMoney(d.amount)}` },
      ...(d.payments||[]).map(p=>({ date:p.date, label:`${this.isOwedToYou(d)?'Received':'Paid'} ${Utils.fmtMoney(p.amount)}${p.notes?' — '+p.notes:''}` })),
      { date:d.dueDate, label:'Due date' }
    ].sort((a,b)=>a.date.localeCompare(b.date));
    Modal.open(`Timeline — ${Utils.escapeHtml(d.borrower)}`, `
      <div class="list">
        ${events.map(e=>`<div class="list-row"><span class="lr-meta">${Utils.fmtDateShort(e.date)}</span><span class="lr-title">${Utils.escapeHtml(e.label)}</span></div>`).join('')}
      </div>
      <div class="modal-foot"><button class="btn" id="tClose">Close</button></div>
    `);
    document.getElementById('tClose').onclick = () => Modal.close();
  },

  deleteDebt(id){
    const d = Store.state.debts.find(x=>x.id===id);
    Modal.confirm(`Delete debt entry for "${d.borrower}"?`, ()=>{
      Store.state.deleted.push({ type:'debt', data:d, ts:Date.now() });
      Store.state.debts = Store.state.debts.filter(x=>x.id!==id);
      Store.logActivity(`Deleted debt entry for ${d.borrower}`, 'debt');
      Core.refreshAllData();
      Toast.show('Debt entry deleted.', { undo: () => { Store.state.debts.push(d); Core.refreshAllData(); } });
    }, { danger:true, okLabel:'Delete' });
  }
};