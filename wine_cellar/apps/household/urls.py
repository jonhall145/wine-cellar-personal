from django.urls import path

from wine_cellar.apps.household import views

urlpatterns = [
    # Household management
    path("", views.HouseholdListView.as_view(), name="household-list"),
    path("create/", views.HouseholdCreateView.as_view(), name="household-create"),
    path("<int:pk>/", views.HouseholdDetailView.as_view(), name="household-detail"),
    path(
        "<int:pk>/settings/",
        views.HouseholdSettingsView.as_view(),
        name="household-settings",
    ),
    path(
        "<int:pk>/rename/",
        views.HouseholdRenameView.as_view(),
        name="household-rename",
    ),
    path(
        "<int:pk>/delete/",
        views.HouseholdDeleteView.as_view(),
        name="household-delete",
    ),
    path(
        "<int:pk>/switch/",
        views.HouseholdSwitchView.as_view(),
        name="household-switch",
    ),
    path("<int:pk>/leave/", views.MemberLeaveView.as_view(), name="household-leave"),
    path(
        "<int:pk>/transfer/",
        views.TransferOwnershipView.as_view(),
        name="household-transfer",
    ),
    # Member management
    path("<int:pk>/invite/", views.MemberInviteView.as_view(), name="member-invite"),
    path(
        "<int:pk>/members/<int:membership_pk>/role/",
        views.MemberUpdateRoleView.as_view(),
        name="member-update-role",
    ),
    path(
        "<int:pk>/members/<int:membership_pk>/remove/",
        views.MemberRemoveView.as_view(),
        name="member-remove",
    ),
    # Invitation management
    path(
        "accept/<str:token>/",
        views.InvitationAcceptView.as_view(),
        name="invitation-accept",
    ),
    path(
        "decline/<str:token>/",
        views.InvitationDeclineView.as_view(),
        name="invitation-decline",
    ),
    path(
        "<int:pk>/invitations/<int:invitation_pk>/cancel/",
        views.InvitationCancelView.as_view(),
        name="invitation-cancel",
    ),
]
