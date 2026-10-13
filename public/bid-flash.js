/* One server-confirmed event per bid; timers share the server's flash timestamp. */
function createBidFlasher({panel, player, auction, serverNow, reducedMotion,
  schedule=setTimeout, cancel=clearTimeout, style=getComputedStyle}) {
 let animation=null;
 const timers=new Set();
 function receive(event) {
  // Reconnection may deliver old events: do not replay old flashes.
  if(!player() || serverNow()-event.flashAt>2000)return;
  const timer=schedule(()=>{
   timers.delete(timer);
   if(!player() || auction()?.id!==event.auction || panel.hidden)return;
   if(animation)animation.cancel();
   const color=event.bidder===player()?'#ff9500':'#ffffff';
   const base=style(panel);
   const frames=reducedMotion()
    ? [{boxShadow:`0 0 0 4px ${color}`},{boxShadow:`0 0 0 4px ${color}`,offset:.8},{boxShadow:'none'}]
    : [{backgroundColor:color,color:'#101713',borderColor:color},
       {backgroundColor:color,color:'#101713',borderColor:color,offset:.2},
       {backgroundColor:base.backgroundColor,color:base.color,borderColor:base.borderColor}];
   panel.classList.add('bid-flashing');
   animation=panel.animate(frames,{duration:600,easing:'ease-out'});
   animation.onfinish=()=>{panel.classList.remove('bid-flashing');animation=null;};
  },Math.max(0,event.flashAt-serverNow()));
  timers.add(timer);
 }
 function reset(){
  for(const timer of timers)cancel(timer);
  timers.clear();if(animation)animation.cancel();animation=null;
  panel.classList.remove('bid-flashing');
 }
 return {receive,reset};
}
if(typeof module!=='undefined')module.exports={createBidFlasher};
