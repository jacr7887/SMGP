// myapp/static/js/jazzmin_custom.js (Versión Final - jQuery y Popup Real)

(function($) {
    $(document).ready(function() {
        // Apuntamos al botón que abre el menú
        $('.navbar-nav .dropdown-toggle').on('click', function(e) {
            e.preventDefault();
            e.stopPropagation();

            let $toggle = $(this);
            let $menu = $toggle.next('.dropdown-menu');

            // Si el menú ya está visible, lo ocultamos
            if ($menu.hasClass('show')) {
                $menu.removeClass('show');
                return;
            }

            // Ocultar cualquier otro menú que esté abierto
            $('.dropdown-menu.show').removeClass('show');

            // Mover el menú al body para que pueda flotar libremente
            $('body').append($menu);

            // Calcular la posición correcta
            let toggleOffset = $toggle.offset();
            let menuWidth = $menu.outerWidth();
            let toggleHeight = $toggle.outerHeight();

            $menu.css({
                position: 'absolute',
                top: toggleOffset.top + toggleHeight + 10, // 10px de espacio debajo del botón
                left: toggleOffset.left + $toggle.outerWidth() - menuWidth // Alinear a la derecha del botón
            });

            // Mostrar el menú con la clase 'show' de Bootstrap
            $menu.addClass('show');
        });

        // Cerrar el menú si se hace clic en cualquier otro lugar de la página
        $(document).on('click', function(e) {
            if (!$(e.target).closest('.dropdown-menu').length && !$(e.target).closest('.dropdown-toggle').length) {
                $('.dropdown-menu.show').removeClass('show');
            }
        });
    });
})(jQuery);