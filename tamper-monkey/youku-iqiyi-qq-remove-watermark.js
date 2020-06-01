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
    var observer = new MutationObserver(function(mutations, observer) {
        for (var mutation of mutations) {
            let target = mutation.target;
            switch (HostName) {
            case "v.qq.com":
                //腾讯视频LOGO水印
                target.querySelector(".txp_waterMark_pic") && target.querySelector(".txp_waterMark_pic").remove();
                //去除广告
                target.querySelectorAll(".site_board_ads").forEach(function(item, index, arr) {
                    item.remove();
                });

                break;
            case "v.youku.com":
                //优酷“极清观影
                target.querySelector(".js-top-icon") && target.querySelector(".js-top-icon").remove();
                //优酷视频LOGO水印
                target.querySelector(".youku-layer-logo") && target.querySelector(".youku-layer-logo").remove();
                break;
            case "www.iqiyi.com":
                //去除广告
                target.querySelectorAll("[data-adzone]").forEach(function(item, index, arr) {
                    item.remove();
                });
                //去除logo
                target.querySelectorAll(".iqp-logo-box").forEach(function(item, index, arr) {
                    item.style.display = 'none';
                });
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
