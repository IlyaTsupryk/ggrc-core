/*!
 Copyright (C) 2017 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

(function (_, GGRC, can) {
  'use strict';

  var tag = 'comment-add-form';
  var template = can.view(GGRC.mustache_path +
    '/components/comment/comment-add-form.mustache');

  /**
   * A component that takes care of adding comments
   *
   */
  GGRC.Components('commentAddForm', {
    tag: tag,
    template: template,
    viewModel: {
      define: {
        instance: {
          value: function () {
            return GGRC.page_instance();
          }
        }
      },
      sendNotifications: true,
      isSaving: false,
      getCommentData: function () {
        var source = this.attr('instance');

        return {
          comment: source.attr('context'),
          send_notification: this.attr('sendNotifications'),
          context: source.context,
          assignee_type: GGRC.Utils.getAssigneeType(source)
        };
      },
      updateComment: function (comment) {
        comment.mark_for_addition('related_objects_as_destination',
          this.attr('instance'));
        comment.attr(this.getCommentData());
        return comment;
      },
      onCommentCreated: function (e) {
        var comment = e.comment;
        this.attr('isSaving', true);

        this.updateComment(comment)
          .save()
          .always(function () {
            this.attr('isSaving', false);
            this.attr('instance').dispatch('refreshInstance');
          }.bind(this));
      }
    }
  });
})(window._, window.GGRC, window.can);
