// ==UserScript==
// @name         pexels复制链接
// @namespace    http://tampermonkey.net/
// @version      0.1
// @description  try to take over the world!
// @author       You
// @include      *://www.pexels.com/*
// @grant        none
// ==/UserScript==

(function () {
    'use strict';
    function onDocumentReady(fn) {
        if (typeof fn !== 'function') {
            return;
        }
        if (document.readyState === 'interactive' || document.readyState === 'complete') {
            return fn();
        }
        document.addEventListener('DOMContentLoaded', fn, false);
    }
    function copyToClipboard(text) {
        if (window.clipboardData && window.clipboardData.setData) {
            // Internet Explorer-specific code path to prevent textarea being shown while dialog is visible.
            return window.clipboardData.setData("Text", text);
        }
        if (document.queryCommandSupported && document.queryCommandSupported("copy")) {
            var textarea = document.createElement("textarea");
            textarea.textContent = text;
            // Prevent scrolling to bottom of page in Microsoft Edge.
            textarea.style.position = "fixed";
            document.body.appendChild(textarea);
            textarea.select();
            try {
                // Security exception may be thrown by some browsers.
                return document.execCommand("copy");
            } catch (ex) {
                console.warn("Copy to clipboard failed.", ex);
                return false;
            } finally {
                document.body.removeChild(textarea);
            }
        }
    }

    onDocumentReady(function () {
        if (!document.querySelector(".rd__button-group.photo-page__action-buttons")) {
            return;
        }
        document.querySelector(".rd__button-group.photo-page__action-buttons").innerHTML += '<button class="rd__button" id="d-link-copy"><span class="js-text">复制链接</span></button>';
        document.querySelector('#d-link-copy').addEventListener('click', function () {
            var link = document.querySelector("a.js-photo-page-image-download-link").href.replace(/[?].+/, "");
            console.log("download link:" + link);
            document.querySelector("#d-link-copy > span").innerText = copyToClipboard(link)? "复制成功√" : "复制失败×";
            setTimeout(function () {
                document.querySelector("#d-link-copy > span").innerText = "复制链接";
            }, 1500);
        })
    })

})();
