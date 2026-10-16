import type { ComponentType, SVGProps } from 'react'
import BroomIcon from '~icons/fluent-emoji-flat/broom'
import CheckIcon from '~icons/fluent-emoji-flat/check-mark-button'
import StarIcon from '~icons/fluent-emoji-flat/glowing-star'
import GearIcon from '~icons/fluent-emoji-flat/gear'
import ProfileIcon from '~icons/fluent-emoji-flat/bust-in-silhouette'
import FamilyIcon from '~icons/fluent-emoji-flat/people-hugging'
import PhotoIcon from '~icons/fluent-emoji-flat/framed-picture'
import SunriseIcon from '~icons/fluent-emoji-flat/sunrise'
import GiftIcon from '~icons/fluent-emoji-flat/wrapped-gift'

type Icon = ComponentType<SVGProps<SVGSVGElement>>

/** Bereiche des Elternbereichs; die Id ist zugleich der Pfad (`/parents/<id>`). */
export const PARENT_AREAS = [
  'profile',
  'review',
  'family',
  'tasks',
  'routines',
  'household',
  'rewards',
  'photos',
  'settings',
] as const
export type ParentArea = (typeof PARENT_AREAS)[number]

/** Entry point for personal settings in the management area. */
export const DEFAULT_AREA: ParentArea = 'profile'

/** The five management tabs replace the everyday navigation. */
export const PRIMARY_AREAS: readonly ParentArea[] = [
  'profile',
  'family',
  'tasks',
  'household',
  'rewards',
]

export const AREA_ICONS: Record<ParentArea, Icon> = {
  profile: ProfileIcon,
  review: CheckIcon,
  family: FamilyIcon,
  tasks: StarIcon,
  routines: SunriseIcon,
  household: BroomIcon,
  rewards: GiftIcon,
  photos: PhotoIcon,
  settings: GearIcon,
}

export const isParentArea = (value: string | undefined): value is ParentArea =>
  PARENT_AREAS.includes(value as ParentArea)

export const areaPath = (area: ParentArea) => `/parents/${area}`
