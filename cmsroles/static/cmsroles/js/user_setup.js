django.jQuery(document).ready(function(){
    $ = django.jQuery;
    $('#add_user_form').submit(function(event){
        event.preventDefault();
        var formData = $(this).serialize();
        $.ajax({
            type: 'POST',
            'url': '/admin/cmsroles/usersetup/adduser/',
            'data': formData, 
            'success': function(data, textStatus){
                if (data.success){
                    $('#user_formset_fields').append(data.user_form);
                    $('#add_user_form_fields').html(data.add_user_form);
                    var user_formset = $('#user_formset #id_form-TOTAL_FORMS');
                    var current_number_of_forms =user_formset.val();
                    user_formset.val(current_number_of_forms + 1);
                    $('#user_formset').show();
                } else {
                    $('#add_user_form_fields').html(data.add_user_form);
                }
            }
        });
        return false;
    });

    $('#site_selector').change(function(){
        var site_pk = $(this).val();
        window.location = '/admin/cmsroles/usersetup/?site=' + site_pk;
    });

});