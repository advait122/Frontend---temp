(function () {
    const toolbar = document.querySelector("[data-student-toolbar]");
    if (!toolbar) {
        return;
    }

    const menus = Array.from(toolbar.querySelectorAll("[data-student-menu]"));
    const notificationCards = Array.from(toolbar.querySelectorAll("[data-notification-card]"));
    let openMenu = null;

    function closeMenu(menu) {
        if (!menu) {
            return;
        }
        const trigger = menu.querySelector("[data-student-menu-trigger]");
        const panel = menu.querySelector("[data-student-menu-panel]");
        menu.classList.remove("is-open");
        if (trigger) {
            trigger.setAttribute("aria-expanded", "false");
        }
        if (panel) {
            panel.hidden = true;
        }
        if (openMenu === menu) {
            openMenu = null;
        }
    }

    function closeAllMenus(exceptMenu) {
        menus.forEach(function (menu) {
            if (menu !== exceptMenu) {
                closeMenu(menu);
            }
        });
    }

    function openMenuPanel(menu) {
        const trigger = menu.querySelector("[data-student-menu-trigger]");
        const panel = menu.querySelector("[data-student-menu-panel]");
        closeAllMenus(menu);
        menu.classList.add("is-open");
        if (trigger) {
            trigger.setAttribute("aria-expanded", "true");
        }
        if (panel) {
            panel.hidden = false;
        }
        openMenu = menu;
    }

    menus.forEach(function (menu) {
        const trigger = menu.querySelector("[data-student-menu-trigger]");
        if (!trigger) {
            return;
        }

        trigger.addEventListener("click", function (event) {
            event.preventDefault();
            const isOpen = menu.classList.contains("is-open");
            if (isOpen) {
                closeMenu(menu);
                return;
            }
            openMenuPanel(menu);
        });
    });

    notificationCards.forEach(function (card) {
        const toggle = card.querySelector("[data-notification-toggle]");
        if (!toggle) {
            return;
        }

        toggle.addEventListener("click", function () {
            const shouldOpen = !card.classList.contains("is-open");
            notificationCards.forEach(function (otherCard) {
                const otherToggle = otherCard.querySelector("[data-notification-toggle]");
                otherCard.classList.remove("is-open");
                if (otherToggle) {
                    otherToggle.setAttribute("aria-expanded", "false");
                }
            });
            card.classList.toggle("is-open", shouldOpen);
            toggle.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
        });
    });

    document.addEventListener("click", function (event) {
        if (!openMenu) {
            return;
        }
        if (openMenu.contains(event.target)) {
            return;
        }
        closeMenu(openMenu);
    });

    document.addEventListener("focusin", function (event) {
        if (!openMenu) {
            return;
        }
        if (openMenu.contains(event.target)) {
            return;
        }
        closeMenu(openMenu);
    });

    document.addEventListener("keydown", function (event) {
        if (event.key !== "Escape" || !openMenu) {
            return;
        }
        const trigger = openMenu.querySelector("[data-student-menu-trigger]");
        closeMenu(openMenu);
        if (trigger) {
            trigger.focus();
        }
    });
})();
