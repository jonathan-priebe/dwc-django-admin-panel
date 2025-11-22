"""
Django models for DWC Server
"""

from django.db import models
from django.utils import timezone


class Console(models.Model):
    """Registered game console (DS, DSi, Wii)"""
    
    PLATFORM_CHOICES = [
        ('DS', 'Nintendo DS'),
        ('DSi', 'Nintendo DSi'),
        ('Wii', 'Nintendo Wii'),
    ]
    
    mac_address = models.CharField(
        max_length=17,
        unique=True,
        db_index=True,
        help_text="Console MAC address (e.g., 00:09:bf:11:22:33)"
    )
    user_id = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Nintendo User ID"
    )
    device_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Console nickname"
    )
    platform = models.CharField(
        max_length=10,
        choices=PLATFORM_CHOICES,
        default='DS'
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Whether this console can connect"
    )
    registered_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'consoles'
        verbose_name = 'Console'
        verbose_name_plural = 'Consoles'
        ordering = ['-last_seen']
    
    def __str__(self):
        name = self.device_name or 'Unnamed Console'
        return f"{name} ({self.mac_address})"


class Profile(models.Model):
    """User profile / Friend Code"""

    profile_id = models.BigAutoField(primary_key=True)
    user_id = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Nintendo User ID"
    )
    game_id = models.CharField(
        max_length=10,
        db_index=True,
        help_text="Game ID (e.g., ADAJ for Pokemon Diamond)"
    )
    console = models.ForeignKey(
        Console,
        on_delete=models.CASCADE,
        related_name='profiles',
        null=True,
        blank=True
    )

    # Authentication
    password = models.CharField(max_length=255, blank=True, help_text="GameSpy password hash")
    email = models.EmailField(blank=True)

    # GameSpy fields
    gs_broadcast_code = models.CharField(max_length=50, blank=True, db_column='gsbrcd')
    uniquenick = models.CharField(max_length=50, blank=True, db_index=True)
    pid = models.CharField(max_length=50, blank=True, help_text="Player ID")

    # Location data
    lon = models.FloatField(null=True, blank=True, help_text="Longitude")
    lat = models.FloatField(null=True, blank=True, help_text="Latitude")
    loc = models.CharField(max_length=100, blank=True, help_text="Location string")
    zipcode = models.CharField(max_length=20, blank=True)

    # Personal info
    firstname = models.CharField(max_length=50, blank=True)
    lastname = models.CharField(max_length=50, blank=True)
    birth = models.CharField(max_length=20, blank=True, help_text="Birthdate")
    aim = models.CharField(max_length=50, blank=True, help_text="AIM username")

    # Console/Device info
    csnum = models.CharField(max_length=50, blank=True, help_text="Console Serial Number")
    cfc = models.CharField(max_length=20, blank=True, help_text="Cached Friend Code")
    bssid = models.CharField(max_length=17, blank=True, help_text="Router MAC address")
    devname = models.CharField(max_length=100, blank=True, help_text="Device name")

    # Status/Stats
    stat = models.TextField(blank=True, help_text="User statistics")
    partnerid = models.IntegerField(null=True, blank=True)

    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'profiles'
        unique_together = ['user_id', 'game_id']
        verbose_name = 'Profile'
        verbose_name_plural = 'Profiles'
        ordering = ['-created_at']
    
    @property
    def friend_code(self):
        """Calculate and return formatted friend code

        Uses the full gs_broadcast_code if available, otherwise falls back to game_id.
        The gsbrcd contains console-specific data that's needed for accurate friend codes.
        """
        try:
            from .friendcode import format_friend_code, generate_friend_code
            # Use gs_broadcast_code if available (full gsbrcd for accurate CRC)
            # Otherwise fall back to game_id (first 4 chars)
            game_code = self.gs_broadcast_code if self.gs_broadcast_code else self.game_id
            fc = generate_friend_code(self.profile_id, game_code)
            return format_friend_code(fc)
        except Exception as e:
            # If something fails, return N/A
            return "N/A"
    
    def __str__(self):
        return f"Profile {self.profile_id} ({self.game_id})"


class NASLogin(models.Model):
    """Nintendo Authentication Server login records"""
    
    user_id = models.CharField(max_length=50, db_index=True)
    auth_token = models.CharField(max_length=255, unique=True)
    data = models.JSONField(help_text="Complete NAS login data")
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()
    
    class Meta:
        db_table = 'nas_logins'
        verbose_name = 'NAS Login'
        verbose_name_plural = 'NAS Logins'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user_id} @ {self.ip_address} ({self.timestamp})"


class AllowList(models.Model):
    """
    MAC Address Whitelist (Original: allow_list)

    Only consoles in this list can connect (if whitelist mode is enabled).
    Based on the original dwc_network_server_emulator allow_list table.
    """

    user_id = models.IntegerField(
        primary_key=True,
        help_text="User ID (console owner)"
    )
    mac_address = models.CharField(
        max_length=17,
        db_column='macadr',
        db_index=True,
        help_text="Console MAC address"
    )
    enabled = models.BooleanField(
        default=True,
        help_text="Whether this whitelist entry is active"
    )
    added_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, help_text="Admin notes")

    class Meta:
        db_table = 'allow_list'
        verbose_name = 'Whitelist Entry'
        verbose_name_plural = 'Whitelist (Allow List)'
        ordering = ['-added_at']

    def __str__(self):
        return f"User {self.user_id} - {self.mac_address}"


class DenyList(models.Model):
    """
    Game-specific Ban List (Original: deny_list)

    Bans a user from a specific game.
    Based on the original dwc_network_server_emulator deny_list table.
    """

    user_id = models.IntegerField(
        db_index=True,
        help_text="User ID to ban"
    )
    game_id = models.CharField(
        max_length=10,
        db_column='gameid',
        db_index=True,
        help_text="Game ID (e.g., ADAJ for Pokemon Diamond)"
    )
    reason = models.TextField(blank=True, help_text="Reason for ban")
    banned_at = models.DateTimeField(auto_now_add=True)
    banned_by = models.CharField(max_length=50, blank=True, help_text="Admin who issued ban")

    class Meta:
        db_table = 'deny_list'
        unique_together = ['user_id', 'game_id']
        verbose_name = 'Game Ban'
        verbose_name_plural = 'Deny List (Game Bans)'
        ordering = ['-banned_at']

    def __str__(self):
        return f"User {self.user_id} banned from {self.game_id}"


class BannedItem(models.Model):
    """
    Generic Ban List (IPs, MACs, Profiles)

    NOTE: For game-specific user bans, use DenyList instead.
    This is for IP/MAC/Profile bans across all games.
    """

    BAN_TYPE_CHOICES = [
        ('ip', 'IP Address'),
        ('mac', 'MAC Address'),
        ('profile', 'Profile ID'),
        ('userid', 'User ID'),
    ]

    ban_type = models.CharField(max_length=10, choices=BAN_TYPE_CHOICES)
    identifier = models.CharField(
        max_length=100,
        db_index=True,
        help_text="The banned identifier (IP, MAC, etc.)"
    )
    reason = models.TextField(blank=True)
    banned_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Leave empty for permanent ban"
    )
    banned_by = models.CharField(max_length=50, blank=True)

    class Meta:
        db_table = 'banned'
        unique_together = ['ban_type', 'identifier']
        verbose_name = 'Banned Item'
        verbose_name_plural = 'Banned Items'
        ordering = ['-banned_at']

    def is_active(self):
        """Check if ban is still active"""
        if self.expires_at:
            return timezone.now() < self.expires_at
        return True

    is_active.boolean = True
    is_active.short_description = 'Active'

    def __str__(self):
        return f"{self.get_ban_type_display()}: {self.identifier}"


class GameServer(models.Model):
    """Registered game servers (from QR server)"""
    
    server_id = models.CharField(max_length=50, unique=True)
    game_name = models.CharField(max_length=50, db_index=True)
    host_profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='hosted_servers',
        null=True,
        blank=True
    )
    
    ip_address = models.GenericIPAddressField()
    port = models.IntegerField()
    
    max_players = models.IntegerField(default=4)
    current_players = models.IntegerField(default=0)
    
    game_data = models.JSONField(
        default=dict,
        help_text="Additional game-specific data"
    )
    
    registered_at = models.DateTimeField(auto_now_add=True)
    last_heartbeat = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'game_servers'
        verbose_name = 'Game Server'
        verbose_name_plural = 'Game Servers'
        ordering = ['-last_heartbeat']
    
    def is_online(self):
        """Check if server sent heartbeat recently (within 2 minutes)"""
        from datetime import timedelta
        threshold = timezone.now() - timedelta(minutes=2)
        return self.last_heartbeat > threshold
    
    is_online.boolean = True
    is_online.short_description = 'Online'
    
    def __str__(self):
        return f"{self.game_name} Server ({self.ip_address}:{self.port})"


class Session(models.Model):
    """Active GameSpy GP sessions"""

    session_key = models.CharField(
        max_length=255,
        primary_key=True,
        help_text="GameSpy session key"
    )
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='sessions',
        db_column='profileid'
    )
    login_time = models.DateTimeField(
        auto_now_add=True,
        db_column='logintime',
        help_text="When the session was created"
    )

    class Meta:
        db_table = 'sessions'
        verbose_name = 'GP Session'
        verbose_name_plural = 'GP Sessions'
        ordering = ['-login_time']

    def is_active(self):
        """Check if session is still active (within last 30 minutes)"""
        from datetime import timedelta
        threshold = timezone.now() - timedelta(minutes=30)
        return self.login_time > threshold

    is_active.boolean = True
    is_active.short_description = 'Active'

    def __str__(self):
        return f"Session for Profile {self.profile.profile_id}"


class Pending(models.Model):
    """Matchmaking queue / Pending game joins"""

    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='pending_matches',
        db_column='profileid'
    )
    group_id = models.IntegerField(
        db_column='groupid',
        help_text="Matchmaking group identifier"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pending'
        unique_together = ['profile', 'group_id']
        verbose_name = 'Pending Match'
        verbose_name_plural = 'Pending Matches'
        ordering = ['-created_at']

    def __str__(self):
        return f"Profile {self.profile.profile_id} in Group {self.group_id}"


class NatNeg(models.Model):
    """NAT Negotiation cookie tracking"""

    cookie = models.BigIntegerField(
        primary_key=True,
        help_text="NAT negotiation cookie"
    )
    client_addr = models.GenericIPAddressField(
        db_column='clientaddr',
        help_text="Client IP address"
    )
    client_port = models.IntegerField(
        db_column='clientport',
        help_text="Client port"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'natneg'
        verbose_name = 'NAT Negotiation'
        verbose_name_plural = 'NAT Negotiations'
        ordering = ['-created_at']

    def __str__(self):
        return f"Cookie {self.cookie} ({self.client_addr}:{self.client_port})"


class ServerStatistic(models.Model):
    """Server statistics snapshot"""

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    active_consoles = models.IntegerField(default=0)
    active_profiles = models.IntegerField(default=0)
    active_servers = models.IntegerField(default=0)
    total_logins_today = models.IntegerField(default=0)

    class Meta:
        db_table = 'server_statistics'
        verbose_name = 'Server Statistic'
        verbose_name_plural = 'Server Statistics'
        ordering = ['-timestamp']
        get_latest_by = 'timestamp'

    def __str__(self):
        return f"Stats @ {self.timestamp}"


class MysteryGift(models.Model):
    """Mystery Gift / DLC for distribution via DLS1 server"""

    # File and identification
    filename = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
        help_text="Mystery Gift filename (e.g., 154p.myg)"
    )
    file = models.FileField(
        upload_to='mystery_gifts/',
        help_text="Upload .myg file"
    )
    file_size = models.IntegerField(
        default=0,
        help_text="File size in bytes (auto-populated)"
    )

    # Game association
    game_id = models.CharField(
        max_length=10,
        db_index=True,
        help_text="Game ID (e.g., CPUE for Pokemon Platinum USA)"
    )

    # Display information
    title = models.CharField(
        max_length=200,
        help_text="Display name (e.g., 'Secret Key Event')"
    )
    description = models.TextField(
        blank=True,
        help_text="Event description"
    )

    # Event metadata
    event_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Type of event (e.g., 'Pokemon', 'Item', 'Unlock')"
    )
    region = models.CharField(
        max_length=10,
        blank=True,
        help_text="Region code (US, EU, JP, etc.)"
    )

    # Availability
    enabled = models.BooleanField(
        default=True,
        help_text="Whether this gift is currently available for download"
    )
    priority = models.IntegerField(
        default=0,
        help_text="Priority for distribution (higher = more important). Used when distribution_mode is 'priority'"
    )
    start_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this gift becomes available (optional)"
    )
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this gift expires (optional)"
    )

    # Statistics
    download_count = models.IntegerField(
        default=0,
        help_text="Number of times downloaded"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.CharField(
        max_length=50,
        blank=True,
        help_text="Admin who created this"
    )

    class Meta:
        db_table = 'mystery_gifts'
        verbose_name = 'Mystery Gift'
        verbose_name_plural = 'Mystery Gifts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['game_id', 'enabled']),
        ]

    def is_available(self):
        """Check if gift is currently available"""
        if not self.enabled:
            return False

        now = timezone.now()

        if self.start_date and now < self.start_date:
            return False

        if self.end_date and now > self.end_date:
            return False

        return True

    is_available.boolean = True
    is_available.short_description = 'Available'

    def save(self, *args, **kwargs):
        """Auto-populate file_size on save"""
        if self.file and not self.file_size:
            self.file_size = self.file.size
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.game_id}) - {self.filename}"


class GameDistributionSettings(models.Model):
    """Distribution settings for Mystery Gifts per game"""

    DISTRIBUTION_MODES = [
        ('random', 'Random - Pick one random gift from available'),
        ('priority', 'Priority - Pick highest priority gift'),
        ('all', 'All - Show all gifts (for non-Pokemon games)'),
    ]

    game_id = models.CharField(
        max_length=10,
        unique=True,
        db_index=True,
        help_text="Game ID (e.g., CPUD for Pokemon Platinum Germany)"
    )
    distribution_mode = models.CharField(
        max_length=20,
        choices=DISTRIBUTION_MODES,
        default='random',
        help_text="How to select which gift to give to the user"
    )
    track_downloads = models.BooleanField(
        default=True,
        help_text="Track which gifts users have already received (prevents duplicates)"
    )
    reset_on_completion = models.BooleanField(
        default=True,
        help_text="When user has all gifts, reset and allow re-downloading"
    )

    class Meta:
        db_table = 'game_distribution_settings'
        verbose_name = 'Game Distribution Setting'
        verbose_name_plural = 'Game Distribution Settings'
        ordering = ['game_id']

    def __str__(self):
        return f"{self.game_id} - {self.get_distribution_mode_display()}"


class MysteryGiftDownload(models.Model):
    """Track Mystery Gift downloads"""

    mystery_gift = models.ForeignKey(
        MysteryGift,
        on_delete=models.CASCADE,
        related_name='downloads'
    )
    profile = models.ForeignKey(
        Profile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mystery_gifts_received',
        help_text="User who downloaded (if tracked)"
    )

    # Download info
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(
        max_length=255,
        blank=True,
        help_text="Client user agent"
    )
    downloaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'mystery_gift_downloads'
        verbose_name = 'Mystery Gift Download'
        verbose_name_plural = 'Mystery Gift Downloads'
        ordering = ['-downloaded_at']
        indexes = [
            models.Index(fields=['mystery_gift', 'downloaded_at']),
            models.Index(fields=['profile', 'downloaded_at']),
        ]

    def __str__(self):
        return f"{self.mystery_gift.filename} @ {self.downloaded_at}"