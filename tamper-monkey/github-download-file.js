// ==UserScript==
// @name         Github Download file
// @namespace    drakulis.pl
// @version      1.1
// @description  Adds Github file download/Raw link
// @author       Drakulis
// @include        https://github.com/*/*
// @require      https://cdn.jsdelivr.net/npm/jquery@3.5.1/dist/jquery.min.js
// @grant        none
// ==/UserScript==

(function($) {

    function addIcons() {
        const $head = $("table.files thead tr");
        if ($head.find("> .download-icon").length > 0) {
            return;
        }

        $head.append($("<th class='download-icon'></th>"))
        $(".up-tree").append($("<td class='download-icon'></td>"));
        $(".up-tree").append($("<td class='download-icon'></td>"));

        $(".js-navigation-item .content a").each(function() {
            const $this = $(this);
            const $item = $this.closest(".js-navigation-item");
            const $iconCol = $item.find(".icon");
            const $downloadCol = $("<td class='download-icon' style='width: 34px'></td>");
            const $jsdelivr_downloadCol = $("<td class='download-icon' style='width: 34px'></td>");

            if ($iconCol.find(".octicon-file").length > 0) {
                const href = $this.attr("href");
                //构造jsDelivr下载链接
                const $jsdelivr_downloadIcon = $('<svg class="octicon octicon-file" viewBox="0 0 16 16" width="16" height="16"><path fill-rule="evenodd" d="M9 12h2l-3 3-3-3h2V7h2v5zm3-8c0-.44-.91-3-4.5-3C5.08 1 3 2.92 3 5 1.02 5 0 6.52 0 8c0 1.53 1 3 3 3h3V9.7H3C1.38 9.7 1.3 8.28 1.3 8c0-.17.05-1.7 1.7-1.7h1.3V5c0-1.39 1.56-2.7 3.2-2.7 2.55 0 3.13 1.55 3.2 1.8v1.2H12c.81 0 2.7.22 2.7 2.2 0 2.09-2.25 2.2-2.7 2.2h-2V11h2c2.08 0 4-1.16 4-3.5C16 5.06 14.08 4 12 4z"></path></svg>');
                const jsdelivr_downloadUrl = "https://cdn.jsdelivr.net/gh" + href.replace(/[/]blob[/][^/]+/, "");
                const $jsdelivr_downloadNode = $("<a href='" + jsdelivr_downloadUrl + "' target='_blank' style='color: #CC6666' title='jsDelivr CDN Raw / Download'></a>");
                $jsdelivr_downloadNode.append($jsdelivr_downloadIcon);
                $jsdelivr_downloadCol.append($jsdelivr_downloadNode);

                //构造github下载链接
                const $downloadIcon = $('<svg class="octicon octicon-file" viewBox="0 0 16 16" width="16" height="16"><path fill-rule="evenodd" d="M9 12h2l-3 3-3-3h2V7h2v5zm3-8c0-.44-.91-3-4.5-3C5.08 1 3 2.92 3 5 1.02 5 0 6.52 0 8c0 1.53 1 3 3 3h3V9.7H3C1.38 9.7 1.3 8.28 1.3 8c0-.17.05-1.7 1.7-1.7h1.3V5c0-1.39 1.56-2.7 3.2-2.7 2.55 0 3.13 1.55 3.2 1.8v1.2H12c.81 0 2.7.22 2.7 2.2 0 2.09-2.25 2.2-2.7 2.2h-2V11h2c2.08 0 4-1.16 4-3.5C16 5.06 14.08 4 12 4z"></path></svg>');
                const downloadUrl = "https://raw.githubusercontent.com" + href.replace("/blob", "");
                const $downloadNode = $("<a href='" + downloadUrl + "' style='color: rgba(3,47,98,.65)' title='Raw / Download'></a>");
                $downloadNode.append($downloadIcon);
                $downloadCol.append($downloadNode);
            }
            $item.append($jsdelivr_downloadCol);
            $item.append($downloadCol);
        });
    }

    //$('body').on('DOMSubtreeModified', '.js-navigation-container ', function(){
    //addIcons();
    //});
    var observer = new MutationObserver(function(mutations, observer) {
        for (var mutation of mutations) {
            if (mutation.target.querySelector('.js-navigation-container')) {
                //console.log(mutation.type);
                //console.log(mutation);
                addIcons();
            }
        }
    });

    observer.observe(document.querySelector('body'), {
        childList: true,
        subtree: true
    });

    addIcons();
}
)(jQuery);
