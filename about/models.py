from django.db import models

# Create your models here.


class About(models.Model):
    """The company's About Us content. Description holds rich text (HTML)
    written in the admin editor."""

    title = models.CharField(max_length=150, default="About Us")
    logo = models.ImageField(upload_to="about/", blank=True)
    description = models.TextField(help_text="Use the toolbar for bold, lists and links.")
    is_active = models.BooleanField(default=True, help_text="Only the active entry is shown.")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-is_active", "-updated_at"]
        verbose_name = "About us"
        verbose_name_plural = "About us"

    def __str__(self):
        return self.title
