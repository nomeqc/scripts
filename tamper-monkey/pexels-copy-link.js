// ==UserScript==
// @name         pexels复制链接
// @namespace    http://tampermonkey.net/
// @version      0.1
// @description  try to take over the world!
// @author       You
// @include      *://www.pexels.com/*
// @require      https://cdn.jsdelivr.net/npm/jquery@3.5.1/dist/jquery.min.js
// @grant        none
// ==/UserScript==

(function() {
    'use strict';
    $(document).ready(function (){
       if(!document.querySelector(".rd__button-group.photo-page__action-buttons")) {
         return;
       }
       document.querySelector(".rd__button-group.photo-page__action-buttons").innerHTML += '<button class="rd__button" id="d-link-copy"><span class="js-text">复制链接</span></button>';
       $("#d-link-copy").click(function (){
         var link = document.querySelector("a.js-photo-page-image-download-link").href.replace(/[?].+/, "");
         console.log("download link:" + link);
         var copyText = function(text) {
             var textarea = document.createElement('textarea');
             document.body.append(textarea);
             textarea.style.position = "absolute";
             textarea.style.left = "-999999px";
             textarea.value = text;
             textarea.select();
             document.execCommand("copy"); // 执行浏览器复制命令
             document.body.removeChild(textarea);
         };
         copyText(link);

         document.querySelector("#d-link-copy > span").innerText = "复制成功√";
         setTimeout(function() {
            document.querySelector("#d-link-copy > span").innerText = "复制链接";
         }, 1500);
       });
    });
})();
