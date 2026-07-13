const Dashboard = {
  esc(s){ return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); },
  fmtAgo(ts){
    if(!ts) return '';
    const d = new Date(ts);
    const sec = Math.max(0, Math.floor((Date.now()-d.getTime())/1000));
    if(sec<60) return sec+'s';
    if(sec<3600) return Math.floor(sec/60)+'m';
    return Math.floor(sec/3600)+'h';
  },
  async fetchJSON(url){
    try{
      const r = await fetch(url,{cache:'no-store'});
      if(!r.ok) throw new Error(r.statusText);
      return await r.json();
    }catch(e){ return {error:e.message}; }
  },
  badge(n){
    return n ? `<span class="cnt">${n}</span>` : '';
  }
};
if(typeof module !== 'undefined') module.exports = Dashboard;
