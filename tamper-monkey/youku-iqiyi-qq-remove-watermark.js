// ==UserScript==
// @name         去除腾讯视频、爱奇艺、优酷视频水印
// @namespace    http://tampermonkey.net/
// @version      0.1
// @description  try to take over the world!
// @author       You
// @match        *://v.youku.com/*
// @match        *://www.iqiyi.com/*
// @match        *://v.qq.com/*
// @grant        none
// ==/UserScript==

var HostName = document.location.hostname;
(()=>{

//         switch(HostName) {
//             case "v.qq.com":
//                 setInterval(()=>{
//                     //腾讯视频LOGO水印
//                     document.querySelector(".txp_waterMark_pic") && document.querySelector(".txp_waterMark_pic").remove();
//                 },1000*0.5);
//                 break;
//             case "v.youku.com":
//                 setInterval(()=>{
//                 //优酷“极清观影
//                 document.querySelector(".js-top-icon") && document.querySelector(".js-top-icon").remove();
//                 //优酷视频LOGO水印
//                 document.querySelector(".youku-layer-logo") && document.querySelector(".youku-layer-logo").remove();
//                 },1000*0.5);
//                 break;
//           case "www.iqiyi.com":
//                 setInterval(()=>{
//                   //爱奇艺LOGO水印
//                   //$(".iqp-logo-box").remove();//为什么这样就不行呢？
//                   document.querySelectorAll(".iqp-logo-box").forEach(function(item,index,arr){item.style.display='none';});
//                 },1000*0.5);
//             break;
//         }

    var observer = new MutationObserver(function(mutations, observer) {
        for (var mutation of mutations) {
            let target = mutation.target;
            switch(HostName) {
            case "v.qq.com":
                //腾讯视频LOGO水印
                target.querySelector(".txp_waterMark_pic") && target.querySelector(".txp_waterMark_pic").remove();
                break;
            case "v.youku.com":
                //优酷“极清观影
                target.querySelector(".js-top-icon") && target.querySelector(".js-top-icon").remove();
                //优酷视频LOGO水印
                target.querySelector(".youku-layer-logo") && target.querySelector(".youku-layer-logo").remove();
                break;
          case "www.iqiyi.com":
                target.querySelectorAll(".iqp-logo-box").forEach(function(item,index,arr){item.style.display='none';});
                break;
        }
        }
    });

    observer.observe(document.querySelector('body'), {
        attributes: true,
        childList: true,
        subtree: true
    });


})();
