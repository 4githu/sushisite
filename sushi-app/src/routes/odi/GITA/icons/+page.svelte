<script lang="ts">
	import AddPhotoCamera from "$lib/odi/components/icons/AddPhotoCamera.svelte";
	import Album from "$lib/odi/components/icons/Album.svelte";
	import BadgeTwo from "$lib/odi/components/icons/BadgeTwo.svelte";
	import Bell from "$lib/odi/components/icons/Bell.svelte";
	import BellAdd from "$lib/odi/components/icons/BellAdd.svelte";
	import BellNotification from "$lib/odi/components/icons/BellNotification.svelte";
	import BellOff from "$lib/odi/components/icons/BellOff.svelte";
	import BellRemove from "$lib/odi/components/icons/BellRemove.svelte";
	import BellRing from "$lib/odi/components/icons/BellRing.svelte";
	import Bookmark from "$lib/odi/components/icons/Bookmark.svelte";
	import BookmarkFill from "$lib/odi/components/icons/BookmarkFill.svelte";
	import Bookmarks from "$lib/odi/components/icons/Bookmarks.svelte";
	import CalendarEvent from "$lib/odi/components/icons/CalendarEvent.svelte";
	import CalenderIcon from "$lib/odi/components/icons/CalenderIcon.svelte";
	import Category from "$lib/odi/components/icons/Category.svelte";
	import ChatConversation from "$lib/odi/components/icons/ChatConversation.svelte";
	import ChatNone from "$lib/odi/components/icons/ChatNone.svelte";
	import Check from "$lib/odi/components/icons/Check.svelte";
	import CheckBox from "$lib/odi/components/icons/CheckBox.svelte";
	import CheckBoxFill from "$lib/odi/components/icons/CheckBoxFill.svelte";
	import ChevronDown from "$lib/odi/components/icons/ChevronDown.svelte";
	import ChevronLeft from "$lib/odi/components/icons/ChevronLeft.svelte";
	import ChevronRight from "$lib/odi/components/icons/ChevronRight.svelte";
	import ChevronUp from "$lib/odi/components/icons/ChevronUp.svelte";
	import Clock from "$lib/odi/components/icons/Clock.svelte";
	import Close from "$lib/odi/components/icons/Close.svelte";
	import Crown from "$lib/odi/components/icons/Crown.svelte";
	import CrownSolid from "$lib/odi/components/icons/CrownSolid.svelte";
	import Declaration from "$lib/odi/components/icons/Declaration.svelte";
	import Drink from "$lib/odi/components/icons/Drink.svelte";
	import Dumbell from "$lib/odi/components/icons/Dumbell.svelte";
	import Ellipse from "$lib/odi/components/icons/Ellipse.svelte";
	import Ellipse1122 from "$lib/odi/components/icons/Ellipse1122.svelte";
	import GraduationCap from "$lib/odi/components/icons/GraduationCap.svelte";
	import Group from "$lib/odi/components/icons/Group.svelte";
	import Group911 from "$lib/odi/components/icons/Group911.svelte";
	import Heart from "$lib/odi/components/icons/Heart.svelte";
	import Icon from "$lib/odi/components/icons/Icon.svelte";
	import Inbox from "$lib/odi/components/icons/Inbox.svelte";
	import LocationPoint from "$lib/odi/components/icons/LocationPoint.svelte";
	import Lock from "$lib/odi/components/icons/Lock.svelte";
	import LockOpen from "$lib/odi/components/icons/LockOpen.svelte";
	import Logo from "$lib/odi/components/icons/Logo.svelte";
	import Megaphone from "$lib/odi/components/icons/Megaphone.svelte";
	import Note from "$lib/odi/components/icons/Note.svelte";
	import PaperPlane from "$lib/odi/components/icons/PaperPlane.svelte";
	import Pencil from "$lib/odi/components/icons/Pencil.svelte";
	import Photo from "$lib/odi/components/icons/Photo.svelte";
	import PhotoCamera from "$lib/odi/components/icons/PhotoCamera.svelte";
	import PhotoCameraOff from "$lib/odi/components/icons/PhotoCameraOff.svelte";
	import Plus from "$lib/odi/components/icons/Plus.svelte";
	import Polygon from "$lib/odi/components/icons/Polygon.svelte";
	import Rectangle from "$lib/odi/components/icons/Rectangle.svelte";
	import Refresh from "$lib/odi/components/icons/Refresh.svelte";
	import Religion from "$lib/odi/components/icons/Religion.svelte";
	import Reload from "$lib/odi/components/icons/Reload.svelte";
	import Rotate from "$lib/odi/components/icons/Rotate.svelte";
	import RotateClockwise from "$lib/odi/components/icons/RotateClockwise.svelte";
	import Ruler from "$lib/odi/components/icons/Ruler.svelte";
	import Settings from "$lib/odi/components/icons/Settings.svelte";
	import ShareAndroid from "$lib/odi/components/icons/ShareAndroid.svelte";
	import ShieldGood from "$lib/odi/components/icons/ShieldGood.svelte";
	import Smoking from "$lib/odi/components/icons/Smoking.svelte";
	import Suitcase from "$lib/odi/components/icons/Suitcase.svelte";
	import User from "$lib/odi/components/icons/User.svelte";
	import UserCheck from "$lib/odi/components/icons/UserCheck.svelte";
	import UserMinus from "$lib/odi/components/icons/UserMinus.svelte";
	import UserPlus from "$lib/odi/components/icons/UserPlus.svelte";
	import UserX from "$lib/odi/components/icons/UserX.svelte";
	import Users from "$lib/odi/components/icons/Users.svelte";
	import Vector from "$lib/odi/components/icons/Vector.svelte";
	import WavyCheck from "$lib/odi/components/icons/WavyCheck.svelte";

	const icons = [
		["AddPhotoCamera", AddPhotoCamera],
		["Album", Album],
		["BadgeTwo", BadgeTwo],
		["Bell", Bell],
		["BellAdd", BellAdd],
		["BellNotification", BellNotification],
		["BellOff", BellOff],
		["BellRemove", BellRemove],
		["BellRing", BellRing],
		["Bookmark", Bookmark],
		["BookmarkFill", BookmarkFill],
		["Bookmarks", Bookmarks],
		["CalendarEvent", CalendarEvent],
		["CalenderIcon", CalenderIcon],
		["Category", Category],
		["ChatConversation", ChatConversation],
		["ChatNone", ChatNone],
		["Check", Check],
		["CheckBox", CheckBox],
		["CheckBoxFill", CheckBoxFill],
		["ChevronDown", ChevronDown],
		["ChevronLeft", ChevronLeft],
		["ChevronRight", ChevronRight],
		["ChevronUp", ChevronUp],
		["Clock", Clock],
		["Close", Close],
		["Crown", Crown],
		["CrownSolid", CrownSolid],
		["Declaration", Declaration],
		["Drink", Drink],
		["Dumbell", Dumbell],
		["Ellipse", Ellipse],
		["Ellipse1122", Ellipse1122],
		["GraduationCap", GraduationCap],
		["Group", Group],
		["Group911", Group911],
		["Heart", Heart],
		["Icon", Icon],
		["Inbox", Inbox],
		["LocationPoint", LocationPoint],
		["Lock", Lock],
		["LockOpen", LockOpen],
		["Logo", Logo],
		["Megaphone", Megaphone],
		["Note", Note],
		["PaperPlane", PaperPlane],
		["Pencil", Pencil],
		["Photo", Photo],
		["PhotoCamera", PhotoCamera],
		["PhotoCameraOff", PhotoCameraOff],
		["Plus", Plus],
		["Polygon", Polygon],
		["Rectangle", Rectangle],
		["Refresh", Refresh],
		["Religion", Religion],
		["Reload", Reload],
		["Rotate", Rotate],
		["RotateClockwise", RotateClockwise],
		["Ruler", Ruler],
		["Settings", Settings],
		["ShareAndroid", ShareAndroid],
		["ShieldGood", ShieldGood],
		["Smoking", Smoking],
		["Suitcase", Suitcase],
		["User", User],
		["UserCheck", UserCheck],
		["UserMinus", UserMinus],
		["UserPlus", UserPlus],
		["UserX", UserX],
		["Users", Users],
		["Vector", Vector],
		["WavyCheck", WavyCheck]
	];
</script>

<div class="grid">
	{#each icons as [name, Component]}
		<div class="card">
			<Component />
			<div class="text-caption">{name}</div>
		</div>
	{/each}
</div>

<style>
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
		gap: 20px;
		padding: 24px;
	}

	.card {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 12px;
		padding: 16px;
		border: 1px solid var(--border);
		border-radius: var(--radius-sm);
		background: var(--surface);
	}

	.card :global(svg) {
		width: 32px;
		height: 32px;
	}

	.text-caption {
		text-align: center;
		word-break: break-word;
	}
</style>