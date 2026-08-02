<script lang="ts">
	import AddPhotoCamera from '$lib/odi/components/icons/molloo/AddPhotoCamera.svelte';
	import Album from '$lib/odi/components/icons/molloo/Album.svelte';
	import BadgeTwo from '$lib/odi/components/icons/molloo/BadgeTwo.svelte';
	import Bell from '$lib/odi/components/icons/molloo/Bell.svelte';
	import BellAdd from '$lib/odi/components/icons/molloo/BellAdd.svelte';
	import BellNotification from '$lib/odi/components/icons/molloo/BellNotification.svelte';
	import BellOff from '$lib/odi/components/icons/molloo/BellOff.svelte';
	import BellRemove from '$lib/odi/components/icons/molloo/BellRemove.svelte';
	import BellRing from '$lib/odi/components/icons/molloo/BellRing.svelte';
	import Bookmark from '$lib/odi/components/icons/molloo/Bookmark.svelte';
	import BookmarkFill from '$lib/odi/components/icons/molloo/BookmarkFill.svelte';
	import Bookmarks from '$lib/odi/components/icons/molloo/Bookmarks.svelte';
	import CalendarEvent from '$lib/odi/components/icons/molloo/CalendarEvent.svelte';
	import CalenderIcon from '$lib/odi/components/icons/molloo/CalenderIcon.svelte';
	import Category from '$lib/odi/components/icons/molloo/Category.svelte';
	import ChatConversation from '$lib/odi/components/icons/molloo/ChatConversation.svelte';
	import ChatNone from '$lib/odi/components/icons/molloo/ChatNone.svelte';
	import Check from '$lib/odi/components/icons/molloo/Check.svelte';
	import CheckBox from '$lib/odi/components/icons/molloo/CheckBox.svelte';
	import CheckBoxFill from '$lib/odi/components/icons/molloo/CheckBoxFill.svelte';
	import ChevronDown from '$lib/odi/components/icons/molloo/ChevronDown.svelte';
	import ChevronLeft from '$lib/odi/components/icons/molloo/ChevronLeft.svelte';
	import ChevronRight from '$lib/odi/components/icons/molloo/ChevronRight.svelte';
	import ChevronUp from '$lib/odi/components/icons/molloo/ChevronUp.svelte';
	import Clock from '$lib/odi/components/icons/molloo/Clock.svelte';
	import Close from '$lib/odi/components/icons/molloo/Close.svelte';
	import Crown from '$lib/odi/components/icons/molloo/Crown.svelte';
	import CrownSolid from '$lib/odi/components/icons/molloo/CrownSolid.svelte';
	import Declaration from '$lib/odi/components/icons/molloo/Declaration.svelte';
	import Drink from '$lib/odi/components/icons/molloo/Drink.svelte';
	import Dumbell from '$lib/odi/components/icons/molloo/Dumbell.svelte';
	import Ellipse from '$lib/odi/components/icons/molloo/Ellipse.svelte';
	import Ellipse1122 from '$lib/odi/components/icons/molloo/Ellipse1122.svelte';
	import GraduationCap from '$lib/odi/components/icons/molloo/GraduationCap.svelte';
	import Group from '$lib/odi/components/icons/molloo/Group.svelte';
	import Group911 from '$lib/odi/components/icons/molloo/Group911.svelte';
	import Heart from '$lib/odi/components/icons/molloo/Heart.svelte';
	import Icon from '$lib/odi/components/icons/molloo/Icon.svelte';
	import Inbox from '$lib/odi/components/icons/molloo/Inbox.svelte';
	import LocationPoint from '$lib/odi/components/icons/molloo/LocationPoint.svelte';
	import Lock from '$lib/odi/components/icons/molloo/Lock.svelte';
	import LockOpen from '$lib/odi/components/icons/molloo/LockOpen.svelte';
	import Logo from '$lib/odi/components/icons/molloo/Logo.svelte';
	import Megaphone from '$lib/odi/components/icons/molloo/Megaphone.svelte';
	import Note from '$lib/odi/components/icons/molloo/Note.svelte';
	import PaperPlane from '$lib/odi/components/icons/molloo/PaperPlane.svelte';
	import Pencil from '$lib/odi/components/icons/molloo/Pencil.svelte';
	import Photo from '$lib/odi/components/icons/molloo/Photo.svelte';
	import PhotoCamera from '$lib/odi/components/icons/molloo/PhotoCamera.svelte';
	import PhotoCameraOff from '$lib/odi/components/icons/molloo/PhotoCameraOff.svelte';
	import Plus from '$lib/odi/components/icons/molloo/Plus.svelte';
	import Polygon from '$lib/odi/components/icons/molloo/Polygon.svelte';
	import Rectangle from '$lib/odi/components/icons/molloo/Rectangle.svelte';
	import Refresh from '$lib/odi/components/icons/molloo/Refresh.svelte';
	import Religion from '$lib/odi/components/icons/molloo/Religion.svelte';
	import Reload from '$lib/odi/components/icons/molloo/Reload.svelte';
	import Rotate from '$lib/odi/components/icons/molloo/Rotate.svelte';
	import RotateClockwise from '$lib/odi/components/icons/molloo/RotateClockwise.svelte';
	import Ruler from '$lib/odi/components/icons/molloo/Ruler.svelte';
	import Settings from '$lib/odi/components/icons/molloo/Settings.svelte';
	import ShareAndroid from '$lib/odi/components/icons/molloo/ShareAndroid.svelte';
	import ShieldGood from '$lib/odi/components/icons/molloo/ShieldGood.svelte';
	import Smoking from '$lib/odi/components/icons/molloo/Smoking.svelte';
	import Suitcase from '$lib/odi/components/icons/molloo/Suitcase.svelte';
	import User from '$lib/odi/components/icons/molloo/User.svelte';
	import UserCheck from '$lib/odi/components/icons/molloo/UserCheck.svelte';
	import UserMinus from '$lib/odi/components/icons/molloo/UserMinus.svelte';
	import UserPlus from '$lib/odi/components/icons/molloo/UserPlus.svelte';
	import UserX from '$lib/odi/components/icons/molloo/UserX.svelte';
	import Users from '$lib/odi/components/icons/molloo/Users.svelte';
	import Vector from '$lib/odi/components/icons/molloo/Vector.svelte';
	import WavyCheck from '$lib/odi/components/icons/molloo/WavyCheck.svelte';

	const icons = [
		['AddPhotoCamera', AddPhotoCamera],
		['Album', Album],
		['BadgeTwo', BadgeTwo],
		['Bell', Bell],
		['BellAdd', BellAdd],
		['BellNotification', BellNotification],
		['BellOff', BellOff],
		['BellRemove', BellRemove],
		['BellRing', BellRing],
		['Bookmark', Bookmark],
		['BookmarkFill', BookmarkFill],
		['Bookmarks', Bookmarks],
		['CalendarEvent', CalendarEvent],
		['CalenderIcon', CalenderIcon],
		['Category', Category],
		['ChatConversation', ChatConversation],
		['ChatNone', ChatNone],
		['Check', Check],
		['CheckBox', CheckBox],
		['CheckBoxFill', CheckBoxFill],
		['ChevronDown', ChevronDown],
		['ChevronLeft', ChevronLeft],
		['ChevronRight', ChevronRight],
		['ChevronUp', ChevronUp],
		['Clock', Clock],
		['Close', Close],
		['Crown', Crown],
		['CrownSolid', CrownSolid],
		['Declaration', Declaration],
		['Drink', Drink],
		['Dumbell', Dumbell],
		['Ellipse', Ellipse],
		['Ellipse1122', Ellipse1122],
		['GraduationCap', GraduationCap],
		['Group', Group],
		['Group911', Group911],
		['Heart', Heart],
		['Icon', Icon],
		['Inbox', Inbox],
		['LocationPoint', LocationPoint],
		['Lock', Lock],
		['LockOpen', LockOpen],
		['Logo', Logo],
		['Megaphone', Megaphone],
		['Note', Note],
		['PaperPlane', PaperPlane],
		['Pencil', Pencil],
		['Photo', Photo],
		['PhotoCamera', PhotoCamera],
		['PhotoCameraOff', PhotoCameraOff],
		['Plus', Plus],
		['Polygon', Polygon],
		['Rectangle', Rectangle],
		['Refresh', Refresh],
		['Religion', Religion],
		['Reload', Reload],
		['Rotate', Rotate],
		['RotateClockwise', RotateClockwise],
		['Ruler', Ruler],
		['Settings', Settings],
		['ShareAndroid', ShareAndroid],
		['ShieldGood', ShieldGood],
		['Smoking', Smoking],
		['Suitcase', Suitcase],
		['User', User],
		['UserCheck', UserCheck],
		['UserMinus', UserMinus],
		['UserPlus', UserPlus],
		['UserX', UserX],
		['Users', Users],
		['Vector', Vector],
		['WavyCheck', WavyCheck]
	];
</script>

<div class="grid">
	{#each icons as [name, Component] (name)}
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
