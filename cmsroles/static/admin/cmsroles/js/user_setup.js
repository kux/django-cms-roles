django.jQuery(document).ready(function(){

    var $ = django.jQuery;

    var current_site = $("#site_selector [selected='selected']").val()

    function set_hidden_site_values(){
        $('input[name*="site"]').val(current_site)
    };

    set_hidden_site_values();

    $('.user_settings').formset({
        addText: 'Assign another user to this site',
        deleteText: '',
        added: function(row){
            set_hidden_site_values();
            $('select', row).chosen({search_contains: true});
        },
    });

    $('#site_selector').change(function(){
        var site_pk = $(this).val();
        window.location = '/admin/cmsroles/usersetup/?site=' + site_pk;
    });

    function submit_userformset(next_action){
        $('#next_on_save').attr('value', next_action);
        $('#user_formset').submit();
    }

    $('#save').click(function(){
        submit_userformset('save');
    });

    $('#save_and_continue').click(function(){
        submit_userformset('continue');
    });

    $('select').chosen({
        search_contains: true
    });

});
