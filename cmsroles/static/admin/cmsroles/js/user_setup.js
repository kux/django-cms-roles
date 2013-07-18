django.jQuery(document).ready(function(){
    var $ = django.jQuery;
    $('#add_user_form').submit(function(event){
        event.preventDefault();
        var form_count_mgmt = $('#user_formset #id_form-TOTAL_FORMS');
        var form_count = parseInt(form_count_mgmt.val());
        $('#add_user_form_count').val(form_count);
        var formData = $(this).serialize();
        $.ajax({
            type: 'POST',
            'url': '/admin/cmsroles/usersetup/adduser/',
            'data': formData, 
            'success': function(data, textStatus){
                if (data.success){
                    $('#user_formset_fields').append(data.user_form);
                    $('#add_user_form_fields').html(data.add_user_form);
                    form_count_mgmt.val(form_count + 1);
                    $('#user_formset').show();
                } else {
                    $('#add_user_form_fields').html(data.add_user_form);
                }
            }
        });
        return false;
    });
    $('#add_user_button').click(function(){
        $('#add_user_form').submit();
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

});
