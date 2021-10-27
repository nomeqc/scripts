// ==UserScript==
// @name         Github 优化【jsdelivr cdn加速】【README链接新窗口打开】
// @version      0.1
// @description  Adds Github file download/Raw link
// @author       Fallrainy
// @include      https://github.com/*/*
// @grant        none
// ==/UserScript==

(function() {

    function parseElement(htmlString) {
        return new DOMParser().parseFromString(htmlString, 'text/html').body.firstChild;
    }

    function createDownloadNode(url) {
        let node = parseElement('<div role="gridcell" class="text-gray-light text-right icon-added" style="width:34px;"></div>');
        if (url.length == 0) {
            return node;
        }
        let aNode = parseElement(`<a href="${url}" target="_blank" style="color: #ff5627" title="jsDelivr CDN Download"></a>`);
        let iconNode = parseElement('<svg class="octicon octicon-file" viewBox="0 0 16 16" width="16" height="16"><path fill-rule="evenodd" d="M9 12h2l-3 3-3-3h2V7h2v5zm3-8c0-.44-.91-3-4.5-3C5.08 1 3 2.92 3 5 1.02 5 0 6.52 0 8c0 1.53 1 3 3 3h3V9.7H3C1.38 9.7 1.3 8.28 1.3 8c0-.17.05-1.7 1.7-1.7h1.3V5c0-1.39 1.56-2.7 3.2-2.7 2.55 0 3.13 1.55 3.2 1.8v1.2H12c.81 0 2.7.22 2.7 2.2 0 2.09-2.25 2.2-2.7 2.2h-2V11h2c2.08 0 4-1.16 4-3.5C16 5.06 14.08 4 12 4z"></path></svg>');
        aNode.append(iconNode);
        node.append(aNode);
        return node;
    }

    function createPaddingNode() {
        let node = parseElement('<div role="gridcell" class="text-gray-light text-right icon-added" style="width:30px;"></div>');
        return node;
    }

    function createRawNode(url) {
        let node = parseElement('<div role="gridcell" class="text-gray-light text-right icon-added" style="width:34px;"></div>');
        if (url.length == 0) {
            return node;
        }
        let aNode = parseElement(`<a href="${url}" target="_blank" style="color: #57606a" title="Raw / Download"></a>`);
        let iconNode = parseElement('<svg class="octicon octicon-file" viewBox="0 0 16 16" width="16" height="16"><path fill-rule="evenodd" d="M9 12h2l-3 3-3-3h2V7h2v5zm3-8c0-.44-.91-3-4.5-3C5.08 1 3 2.92 3 5 1.02 5 0 6.52 0 8c0 1.53 1 3 3 3h3V9.7H3C1.38 9.7 1.3 8.28 1.3 8c0-.17.05-1.7 1.7-1.7h1.3V5c0-1.39 1.56-2.7 3.2-2.7 2.55 0 3.13 1.55 3.2 1.8v1.2H12c.81 0 2.7.22 2.7 2.2 0 2.09-2.25 2.2-2.7 2.2h-2V11h2c2.08 0 4-1.16 4-3.5C16 5.06 14.08 4 12 4z"></path></svg>');
        aNode.append(iconNode);
        node.append(aNode);
        return node;
    }

    function addIcons() {
        if(document.querySelector('.icon-added')) {
           return;
        }
        let nodes = document.querySelectorAll("div[aria-labelledby] > div.js-navigation-item");
        for (let row of nodes) {
            let isFile = row.querySelector('svg[aria-label=File]');
            if (isFile) {
                let href = row.querySelector('div[role=rowheader] > span > a').getAttribute('href');
                const downloadUrl = "https://cdn.jsdelivr.net/gh" + href.replace(/[/]blob[/][^/]+/, "");
                const rawUrl = "https://raw.githubusercontent.com" + href.replace("/blob", "");
                const downloadUrlNode = createDownloadNode(downloadUrl);
                const rawUrlNode = createRawNode(rawUrl);
                const paddingNode = createPaddingNode('');
                row.insertBefore(paddingNode, row.children[2]);
                row.insertBefore(rawUrlNode, paddingNode);
                row.insertBefore(downloadUrlNode, rawUrlNode);
            } else {
                const downloadUrlNode = createDownloadNode('');
                const rawUrlNode = createRawNode('');
                const paddingNode = createPaddingNode('');
                row.insertBefore(paddingNode, row.children[2]);
                row.insertBefore(rawUrlNode, paddingNode);
                row.insertBefore(downloadUrlNode, rawUrlNode);
            }
        }
    }

    var observer = new MutationObserver(function(mutations, observer) {
        for (var mutation of mutations) {
            if (mutation.target.querySelector('.js-navigation-container')) {
                //console.log(mutation.type);
                //console.log(mutation);
                addIcons();
            }
            if(mutation.target.querySelector('article.markdown-body')) {
                let readmeAllLink = document.querySelector('article.markdown-body').querySelectorAll('a[href^="http"]')
                for(let link of readmeAllLink) {
                  link.setAttribute('target', '_blank')
                }
            }
        }
    }
    );

    observer.observe(document.querySelector('body'), {
        childList: true,
        subtree: true
    });

    addIcons();
}
)();
