from django.core.validators import MinValueValidator
from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)


class Game(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="games"
    )
    name = models.CharField(max_length=120)
    description = models.TextField(max_length=2000)
    min_players = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    max_players = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    duration_minutes = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(min_players__gte=1)
                & models.Q(max_players__gte=models.F("min_players"))
                & models.Q(duration_minutes__gte=1),
                name="game_valid_players_and_duration",
            )
        ]


class Venue(models.Model):
    name = models.CharField(max_length=120)
    city = models.CharField(max_length=80)
    address = models.CharField(max_length=200)
    description = models.TextField(max_length=2000)
