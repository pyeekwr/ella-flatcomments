from django.contrib import comments
from django.db.models import Max

from ella_flatcomments.models import FlatComment, redis

def show_reversed(request):
    reverse = False
    # TODO: maybe also pass in the content_type to makethe decision
    if 'reverse' in request.GET:
        reverse = bool(request.GET['reverse'])
    return reverse

def disconnect_legacy_signals():
    " Disconnect signals for ell-comments to allow tests and migrations to run. "
    from ella.core.signals import content_published, content_unpublished
    from ella_comments.listing_handlers import publishable_published, publishable_unpublished

    content_published.disconnect(publishable_published)
    content_unpublished.disconnect(publishable_unpublished)

def migrate_legacy_comments():
    from ella_flatcomments.register import comment_posted
    CommentModel = comments.get_model()
    if not CommentModel._meta.installed:
        return

    migrated_id = FlatComment.objects.all().aggregate(Max('id'))['id__max'] or 0
    cnt = 0
    for c in CommentModel.objects.exclude(user__isnull=True).order_by('id').filter(id__gt=migrated_id).iterator():
        fc = FlatComment(
            id=c.pk,
            site_id=c.site_id,
            content_type_id=c.content_type_id,
            object_id=c.object_pk,

            submit_date=c.submit_date,
            user=c.user,
            comment=c.comment,

            is_public=c.is_public and not c.is_removed,
        )

        fc.save(force_insert=True)
        if fc.is_public:
            redis.lpush(fc._comment_list()._key, c.pk)
            comment_posted(fc)
        cnt += 1
    return cnt
