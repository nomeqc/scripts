// ==UserScript==
// @name         宝塔面板_文件管理_复制路径
// @namespace    http://tampermonkey.net/
// @version      0.1
// @description  try to take over the world!
// @author       You
// @include        http*://*:8822/files
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

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

    function loadCssCode(code) {
        let style = document.createElement('style');
        style.type = 'text/css';
        style.rel = 'stylesheet';
        try {
            //for Chrome Firefox Opera Safari
            style.appendChild(document.createTextNode(code));
        } catch (ex) {
            //for IE
            style.styleSheet.cssText = code;
        }
        let head = document.getElementsByTagName('head')[0];
        head.appendChild(style);
    }

    function parseElement(htmlString) {
        return new DOMParser().parseFromString(htmlString, 'text/html').body.firstChild;
    }

    function buildCopyBtn() {
        let copyBtnStr = `<span class="copy-path-btn">复制路径</span>`
        let copyBtn = parseElement(copyBtnStr)
        copyBtn.addEventListener('click', function(e) {
            //         console.log(this)
            this.textContent = copyToClipboard(this.previousSibling.title) ? "复制成功✔" : "复制失败"
            setTimeout(() => {
                this.textContent = "复制路径"
            }, 1000)
            e.stopPropagation()
        })
        return copyBtn
    }

    function addCopyBtns() {
        for (let parent of document.querySelectorAll('.file_td.file_name')) {
            parent.appendChild(buildCopyBtn())
        }
    }

    function setup() {
        loadCssCode(`
        .copy-path-btn{
            display: none;
            position: absolute;
            right: 100px;
            cursor: pointer;
            padding: 0px 10px;
            color: #20a53a;
        }
        .file_tr:hover .copy-path-btn{
            display:inline-block
        }
        .file_tr.active .copy-path-btn {
            display: inline-block!important
        }`)

        var observer = new MutationObserver(function(mutations, observer) {
            for (var mutation of mutations) {
                if (document.querySelector('.file_td.file_name') && !document.querySelector('.copy-path-btn')) {
                    //console.log(mutation.type);
                    //console.log(mutation);
                    addCopyBtns();
                }
            }
        });

        observer.observe(document.querySelector('body'), {
            childList: true,
            subtree: true
        });
        addCopyBtns()
    }
    setup()

})();
