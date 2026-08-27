/* Eklavya Education Complex — behaviour. OWNER is single config point. */
var OWNER={whatsapp:"",phone:"",address:"",hours:"",mapsQuery:"",email:""};
(function(){
"use strict";
var header=document.querySelector(".site-header");
if(header){
  var s=function(){header.classList.toggle("is-scrolled",scrollY>8)};
  addEventListener("scroll",s,{passive:true});s();
}
var els=document.querySelectorAll(".reveal");
if("IntersectionObserver" in window && !matchMedia("(prefers-reduced-motion: reduce)").matches){
  var m=new Map();
  els.forEach(function(el){
    var g=el.closest("section,header,footer")||document.body;
    if(!m.has(g))m.set(g,0);
    el.style.setProperty("--d",Math.min(m.get(g),480)+"ms");
    m.set(g,m.get(g)+80);
  });
  var io=new IntersectionObserver(function(es){
    es.forEach(function(e){if(e.isIntersecting){e.target.classList.add("in");io.unobserve(e.target)}});
  },{threshold:.12,rootMargin:"0px 0px -40px"});
  els.forEach(function(e){io.observe(e)});
}else{els.forEach(function(e){e.classList.add("in")})}
document.querySelectorAll("[data-owner-link]").forEach(function(a){
  var k=a.getAttribute("data-owner-link"),href="";
  if(k==="whatsapp"&&OWNER.whatsapp)href="https://wa.me/"+OWNER.whatsapp;
  else if(k==="tel"&&OWNER.phone)href="tel:"+OWNER.phone.replace(/[^+\d]/g,"");
  else if(k==="maps"&&OWNER.mapsQuery)href="https://www.google.com/maps/search/?api=1&query="+encodeURIComponent(OWNER.mapsQuery);
  else if(k==="email"&&OWNER.email)href="mailto:"+OWNER.email;
  if(href){a.href=href;a.classList.remove("is-disabled");a.removeAttribute("aria-disabled")}
});
document.querySelectorAll("[data-owner-text]").forEach(function(el){
  var k=el.getAttribute("data-owner-text");
  if(OWNER[k])el.textContent=OWNER[k];
});
var comp=document.querySelector("[data-composer]");
if(comp){
  var chips=comp.querySelectorAll(".chip"),note=comp.querySelector("#inq-note"),nameF=comp.querySelector("#inq-name"),prev=comp.querySelector("#inq-preview"),copyBtn=comp.querySelector("#inq-copy"),waBtn=comp.querySelector("#inq-wa"),mailBtn=comp.querySelector("#inq-mail");
  var build=function(){
    var subj=comp.querySelector('.chip[aria-pressed="true"]');
    var topic=subj?subj.textContent.trim():"General enquiry";
    var n=(nameF&&nameF.value||"").trim();
    var d=(note&&note.value||"").trim();
    var lines=["Namaste Eklavya Education Complex,",""];
    lines.push("I would like to ask about: "+topic);
    if(n)lines.push("Name: "+n);
    if(d)lines.push("",d);
    lines.push("","(sent from eklavyaeducationcomplex.in)");
    return lines.join("\n");
  };
  var render=function(){
    var t=build();
    prev.textContent=t;
    var enc=encodeURIComponent(t);
    if(waBtn){
      if(OWNER.whatsapp)waBtn.href="https://wa.me/"+OWNER.whatsapp+"?text="+enc;
      else waBtn.href="https://wa.me/?text="+enc;
      waBtn.classList.remove("is-disabled");waBtn.removeAttribute("aria-disabled");
    }
    if(mailBtn){
      var subj=comp.querySelector('.chip[aria-pressed="true"]');
      var subjTxt=subj?subj.textContent.trim():"Enquiry";
      var to=OWNER.email||"";
      mailBtn.href="mailto:"+to+"?subject="+encodeURIComponent(subjTxt+" — Eklavya Education Complex")+"&body="+enc;
      mailBtn.classList.remove("is-disabled");mailBtn.removeAttribute("aria-disabled");
    }
  };
  chips.forEach(function(c){
    c.addEventListener("click",function(){
      chips.forEach(function(x){x.setAttribute("aria-pressed",x===c?"true":"false")});
      render();
    });
  });
  if(note)note.addEventListener("input",render);
  if(nameF)nameF.addEventListener("input",render);
  render();
  if(copyBtn)copyBtn.addEventListener("click",function(){
    var txt=prev.textContent;
    var done=function(){copyBtn.classList.remove("copy-flash");void copyBtn.offsetWidth;copyBtn.classList.add("copy-flash");var o=copyBtn.textContent;copyBtn.textContent="Copied ✓";setTimeout(function(){copyBtn.textContent=o},1600)};
    if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(txt).then(done,done);
    else{var ta=document.createElement("textarea");ta.value=txt;document.body.appendChild(ta);ta.select();try{document.execCommand("copy")}catch(e){}document.body.removeChild(ta);done()}
  });
}
document.querySelectorAll("[data-year]").forEach(function(el){el.textContent=new Date().getFullYear()});
})();
