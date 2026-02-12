import * as React from "react"
import { Check, ChevronsUpDown, User, PlusCircle } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import {
    Command,
    CommandEmpty,
    CommandGroup,
    CommandInput,
    CommandItem,
    CommandList,
    CommandSeparator,
} from "@/components/ui/command"
import {
    Popover,
    PopoverContent,
    PopoverTrigger,
} from "@/components/ui/popover"
import { ProfileListItem } from "@/types"

interface ProfileSelectorProps {
    profiles: ProfileListItem[]
    currentProfileId: string
    onSelect: (id: string) => void
    onCreate: (name: string) => void
    disabled?: boolean
    className?: string
}

export function ProfileSelector({
    profiles,
    currentProfileId,
    onSelect,
    onCreate,
    disabled,
    className,
}: ProfileSelectorProps) {
    const [open, setOpen] = React.useState(false)
    const [query, setQuery] = React.useState("")

    const selectedProfile = profiles.find((p) => p.id === currentProfileId)

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={open}
                    disabled={disabled}
                    className={cn("w-[160px] h-9 justify-between md:w-[140px] lg:w-[160px] text-xs px-2", className)}
                >
                    {selectedProfile ? (
                        <div className="flex items-center gap-2 truncate">
                            <User className="h-3.5 w-3.5 shrink-0 opacity-70" />
                            <span className="truncate">{selectedProfile.name}</span>
                        </div>
                    ) : (
                        <div className="flex items-center gap-2 text-muted-foreground">
                            <User className="h-3.5 w-3.5 shrink-0 opacity-50" />
                            <span>选择归属用户...</span>
                        </div>
                    )}
                    <ChevronsUpDown className="ml-2 h-3 w-3 shrink-0 opacity-50" />
                </Button>
            </PopoverTrigger>
            <PopoverContent className="w-[200px] p-0" align="start">
                <Command>
                    <CommandInput placeholder="搜索用户..." value={query} onValueChange={setQuery} className="h-8 text-xs" />
                    <CommandList>
                        <CommandEmpty>
                            <div className="p-2 text-xs text-center text-muted-foreground">
                                未找到用户
                            </div>
                        </CommandEmpty>
                        <CommandGroup>
                            {profiles.map((profile) => (
                                <CommandItem
                                    key={profile.id}
                                    value={profile.name}
                                    onSelect={() => {
                                        onSelect(profile.id)
                                        setOpen(false)
                                    }}
                                    className="text-xs h-8"
                                >
                                    <Check
                                        className={cn(
                                            "mr-2 h-3 w-3",
                                            currentProfileId === profile.id ? "opacity-100" : "opacity-0"
                                        )}
                                    />
                                    <div className="flex flex-col">
                                        <span>{profile.name}</span>
                                        <span className="text-[10px] text-muted-foreground font-mono">{profile.id}</span>
                                    </div>
                                </CommandItem>
                            ))}
                        </CommandGroup>
                        <CommandSeparator />
                        <CommandGroup>
                            <CommandItem
                                onSelect={() => {
                                    if (query.trim()) {
                                        onCreate(query.trim())
                                        setOpen(false)
                                        setQuery("")
                                    }
                                }}
                                disabled={!query.trim()}
                                className="text-xs h-8"
                            >
                                <PlusCircle className="mr-2 h-3.5 w-3.5" />
                                {query.trim() ? `创建 "${query.trim()}"` : "输入名称创建"}
                            </CommandItem>
                        </CommandGroup>
                    </CommandList>
                </Command>
            </PopoverContent>
        </Popover>
    )
}
