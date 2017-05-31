/*!
 Copyright (C) 2017 Google Inc.
 Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
 */

(function (can, GGRC) {
  'use strict';

  var tpl = can.view(GGRC.mustache_path +
    '/components/ca-object/ca-object-modal-content.mustache');

  can.Component.extend({
    tag: 'ca-object-modal-content',
    template: tpl,
    viewModel: {
      define: {
        comment: {
          get: function () {
            return this.attr('content.fields').indexOf('comment') > -1 &&
              this.attr('state.open');
          }
        },
        evidence: {
          get: function () {
            return this.attr('content.fields').indexOf('evidence') > -1 &&
              this.attr('state.open');
          }
        },
        state: {
          value: {
            open: false,
            save: false,
            controls: false
          }
        }
      },
      allSaved: false,
      formSavedDeferred: can.Deferred(),
      content: {
        contextScope: {},
        fields: [],
        title: '',
        type: 'dropdown',
        value: null,
        options: []
      },
      caIds: {},
      onCommentCreated: function (e) {
        var comment = e.comment;
        var instance = this.attr('instance');
        var context = instance.attr('context');
        var commentUpdate = {
          context: context,
          assignee_type: GGRC.Utils.getAssigneeType(this.attr('instance'))
        };
        var relation = new CMS.Models.Relationship({
          context: context,
          destination: instance
        });

        var addComment = function () {
          return comment.attr(commentUpdate)
            .save()
            .done(function (comment) {
              relation.attr({source: comment.serialize()})
                .save()
                .then(function () {
                  this.attr('instance').dispatch('refreshInstance');
                }.bind(this));
            }.bind(this));
        }.bind(this);

        commentUpdate.custom_attribute_revision_upd = {
          custom_attribute_value: {id: this.attr('caIds.valueId')},
          custom_attribute_definition: {id: this.attr('caIds.defId')}
        };

        this.attr('content.contextScope.errorsMap.comment', false);
        this.attr('content.contextScope.validation.valid',
          !this.attr('content.contextScope.errorsMap.evidence'));
        this.attr('state.open', false);
        this.attr('state.save', false);

        this.attr('formSavedDeferred').then(function () {
          addComment();
        });
      }
    }
  });
})(window.can, window.GGRC);
