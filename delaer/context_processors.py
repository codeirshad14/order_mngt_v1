"""What role the signed-in user has, for every template.

The sidebar needs this to decide which menus to show. Without it the
Attendance link sat there for dealers too, and clicking it only ever earned
them a message saying they could not — a link that always refuses is worse
than no link.

One small query per page, on an indexed one-to-one, and only for a signed-in
user. Django caches the reverse lookup on the user instance, so anything else
in the same request that asks gets it free.
"""


def roles(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"user_is_sales": False, "user_is_manager": False, "user_is_dealer": False}

    # imported here rather than at module level: a context processor is
    # loaded while the app registry is still warming up
    from myorder.views import is_manager, is_sales

    return {
        "user_is_sales": is_sales(user),
        "user_is_manager": is_manager(user),
        "user_is_dealer": hasattr(user, "dealer_profile"),
    }
