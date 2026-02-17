import pytest
from django.db import IntegrityError

from wine_cellar.apps.whisky.models import (
    CaskHistory,
    FillLevel,
    PreviousContents,
    WhiskyRegion,
    WhiskyType,
)


@pytest.mark.django_db
def test_whisky_region_creation(whisky_region_factory):
    """Test that a WhiskyRegion can be created with basic fields."""
    region = whisky_region_factory(name="Speyside", slug="speyside", country="GB")
    assert region.pk is not None
    assert region.name == "Speyside"
    assert region.slug == "speyside"
    assert region.country == "GB"
    assert str(region) == "Speyside"


@pytest.mark.django_db
def test_whisky_region_ordering(whisky_region_factory):
    """Test that WhiskyRegion ordering is by order then name."""
    region_b = whisky_region_factory(name="Islay", order=2)
    region_a = whisky_region_factory(name="Speyside", order=1)
    region_c = whisky_region_factory(name="Highland", order=2)

    regions = list(WhiskyRegion.objects.all())
    assert regions[0] == region_a
    # order=2 regions should be sorted by name: Highland before Islay
    assert regions[1] == region_c
    assert regions[2] == region_b


@pytest.mark.django_db
def test_whisky_region_unique_together(whisky_region_factory):
    """Test that (name, country) must be unique for WhiskyRegion."""
    whisky_region_factory(name="Speyside", slug="speyside-1", country="GB")
    with pytest.raises(IntegrityError):
        whisky_region_factory(name="Speyside", slug="speyside-2", country="GB")


@pytest.mark.django_db
def test_distillery_creation(distillery_factory, whisky_region_factory):
    """Test that a Distillery can be created with region."""
    region = whisky_region_factory(name="Islay")
    distillery = distillery_factory(
        name="Lagavulin",
        region=region,
        country="GB",
        founded_year=1816,
    )
    assert distillery.pk is not None
    assert distillery.name == "Lagavulin"
    assert distillery.region == region
    assert distillery.founded_year == 1816
    assert str(distillery) == "Lagavulin"


@pytest.mark.django_db
def test_distillery_uniqueness_constraint(distillery_factory):
    """Test that (name, country) must be unique for Distillery."""
    distillery_factory(name="Lagavulin", country="GB")
    with pytest.raises(IntegrityError):
        distillery_factory(name="Lagavulin", country="GB")


@pytest.mark.django_db
def test_distillery_same_name_different_country(distillery_factory):
    """Test that distilleries with the same name but different countries are allowed."""
    d1 = distillery_factory(name="TestDistillery", country="GB")
    d2 = distillery_factory(name="TestDistillery", country="JP")
    assert d1.pk != d2.pk


@pytest.mark.django_db
def test_whisky_creation(whisky_factory, user):
    """Test that a Whisky can be created with basic fields."""
    whisky = whisky_factory(
        user=user,
        name="Lagavulin 16",
        whisky_type=WhiskyType.SINGLE_MALT,
        abv=43.0,
        age_statement=16,
        country="GB",
    )
    assert whisky.pk is not None
    assert whisky.name == "Lagavulin 16"
    assert whisky.whisky_type == WhiskyType.SINGLE_MALT
    assert whisky.abv == 43.0
    assert whisky.age_statement == 16
    assert whisky.user == user


@pytest.mark.django_db
def test_whisky_str_with_age_and_abv(whisky_factory, user):
    """Test Whisky __str__ includes age statement and ABV."""
    whisky = whisky_factory(
        user=user,
        name="Talisker",
        age_statement=10,
        abv=45.8,
    )
    result = str(whisky)
    assert "Talisker" in result
    assert "10yo" in result
    assert "45.8%" in result


@pytest.mark.django_db
def test_whisky_str_nas(whisky_factory, user):
    """Test Whisky __str__ for NAS (No Age Statement) whisky."""
    whisky = whisky_factory(
        user=user,
        name="Ardbeg Uigeadail",
        age_statement=None,
        abv=54.2,
    )
    result = str(whisky)
    assert "Ardbeg Uigeadail" in result
    assert "yo" not in result
    assert "54.2%" in result


@pytest.mark.django_db
def test_whisky_is_nas_property(whisky_factory, user):
    """Test the is_nas property."""
    nas_whisky = whisky_factory(user=user, age_statement=None)
    aged_whisky = whisky_factory(user=user, age_statement=12)
    assert nas_whisky.is_nas is True
    assert aged_whisky.is_nas is False


@pytest.mark.django_db
def test_whisky_is_official_bottling(whisky_factory, bottler_factory, user):
    """Test the is_official_bottling property."""
    ob_whisky = whisky_factory(user=user, bottler=None)
    ib_whisky = whisky_factory(user=user, bottler=bottler_factory())
    assert ob_whisky.is_official_bottling is True
    assert ib_whisky.is_official_bottling is False


@pytest.mark.django_db
def test_whisky_total_stock(whisky_factory, whisky_storage_item_factory, user):
    """Test the total_stock property counts non-deleted items."""
    whisky = whisky_factory(user=user)
    storage = user.storage_set.first()
    whisky_storage_item_factory(whisky=whisky, storage=storage)
    whisky_storage_item_factory(whisky=whisky, storage=storage)
    whisky_storage_item_factory(whisky=whisky, storage=storage, deleted=True)

    assert whisky.total_stock == 2


@pytest.mark.django_db
def test_whisky_get_absolute_url(whisky_factory, user):
    """Test get_absolute_url returns the detail URL."""
    whisky = whisky_factory(user=user)
    url = whisky.get_absolute_url()
    assert url == f"/whisky/{whisky.pk}/"


@pytest.mark.django_db
def test_whisky_storage_item_creation(
    whisky_factory, whisky_storage_item_factory, user
):
    """Test WhiskyStorageItem creation with fill_level."""
    whisky = whisky_factory(user=user)
    storage = user.storage_set.first()
    item = whisky_storage_item_factory(
        whisky=whisky,
        storage=storage,
        fill_level=FillLevel.OPENED,
        price=55.00,
    )
    assert item.pk is not None
    assert item.fill_level == FillLevel.OPENED
    assert item.whisky == whisky
    assert item.deleted is False
    assert float(item.price) == 55.00


@pytest.mark.django_db
def test_whisky_storage_item_fill_levels(
    whisky_factory, whisky_storage_item_factory, user
):
    """Test all fill level choices work correctly."""
    whisky = whisky_factory(user=user)
    storage = user.storage_set.first()
    for fill_level_code, _ in FillLevel.choices:
        item = whisky_storage_item_factory(
            whisky=whisky,
            storage=storage,
            fill_level=fill_level_code,
        )
        assert item.fill_level == fill_level_code


@pytest.mark.django_db
def test_whisky_storage_item_str(whisky_factory, whisky_storage_item_factory, user):
    """Test WhiskyStorageItem __str__."""
    whisky = whisky_factory(user=user, name="Laphroaig 10")
    storage = user.storage_set.first()
    item = whisky_storage_item_factory(whisky=whisky, storage=storage, row=2, column=3)
    result = str(item)
    assert "Laphroaig 10" in result
    assert "Row 2" in result
    assert "Col 3" in result


@pytest.mark.django_db
def test_whisky_storage_item_str_unassigned(
    whisky_factory, whisky_storage_item_factory, user
):
    """Test WhiskyStorageItem __str__ when no row/column assigned."""
    whisky = whisky_factory(user=user, name="Oban 14")
    storage = user.storage_set.first()
    item = whisky_storage_item_factory(
        whisky=whisky, storage=storage, row=None, column=None
    )
    result = str(item)
    assert "Oban 14" in result
    assert "Unassigned" in result


@pytest.mark.django_db
def test_cask_history_creation(cask_history_factory, whisky_factory, user):
    """Test CaskHistory creation."""
    whisky = whisky_factory(user=user)
    cask = cask_history_factory(
        whisky=whisky,
        order=1,
        cask_type="Butt",
        previous_contents=PreviousContents.SHERRY_OLOROSO,
        duration_years=12,
        is_finish=False,
    )
    assert cask.pk is not None
    assert cask.whisky == whisky
    assert cask.order == 1
    assert cask.duration_years == 12


@pytest.mark.django_db
def test_cask_history_ordering(cask_history_factory, whisky_factory, user):
    """Test CaskHistory is ordered by whisky then order."""
    whisky = whisky_factory(user=user)
    cask2 = cask_history_factory(whisky=whisky, order=2)
    cask1 = cask_history_factory(whisky=whisky, order=1)
    cask3 = cask_history_factory(whisky=whisky, order=3)

    casks = list(CaskHistory.objects.filter(whisky=whisky))
    assert casks[0] == cask1
    assert casks[1] == cask2
    assert casks[2] == cask3


@pytest.mark.django_db
def test_cask_history_unique_together(cask_history_factory, whisky_factory, user):
    """Test that (whisky, order) must be unique for CaskHistory."""
    whisky = whisky_factory(user=user)
    cask_history_factory(whisky=whisky, order=1)
    with pytest.raises(IntegrityError):
        cask_history_factory(whisky=whisky, order=1)


@pytest.mark.django_db
def test_cask_history_str(cask_history_factory, whisky_factory, user):
    """Test CaskHistory __str__."""
    whisky = whisky_factory(user=user)
    cask = cask_history_factory(
        whisky=whisky,
        order=1,
        cask_type="Butt",
        previous_contents=PreviousContents.SHERRY_OLOROSO,
        duration_years=12,
        is_finish=True,
    )
    result = str(cask)
    assert "Sherry (Oloroso)" in result
    assert "Butt" in result
    assert "(finish)" in result
    assert "12yr" in result


@pytest.mark.django_db
def test_bottler_creation(bottler_factory):
    """Test Bottler creation."""
    bottler = bottler_factory(name="Gordon & MacPhail", short_name="G&M")
    assert bottler.pk is not None
    assert bottler.name == "Gordon & MacPhail"
    assert str(bottler) == "G&M"


@pytest.mark.django_db
def test_bottler_str_without_short_name(bottler_factory):
    """Test Bottler __str__ falls back to name when no short_name."""
    bottler = bottler_factory(name="Signatory Vintage", short_name="")
    assert str(bottler) == "Signatory Vintage"


@pytest.mark.django_db
def test_whisky_display_type(whisky_factory, user):
    """Test the display_type property."""
    whisky = whisky_factory(user=user, whisky_type=WhiskyType.SINGLE_MALT)
    assert whisky.display_type == "Single Malt"

    whisky_blended = whisky_factory(user=user, whisky_type=WhiskyType.BLENDED)
    assert whisky_blended.display_type == "Blended"
