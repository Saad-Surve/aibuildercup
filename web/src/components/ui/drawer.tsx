"use client";

import { Dialog as DialogPrimitive } from "@base-ui/react/dialog";
import { cn } from "cn";

/**
 * A right-hand drawer built on the Base UI dialog primitive.
 *
 * Used by the draft editor for alternatives. It is deliberately **non-modal**:
 * the document behind it stays visible and interactive so a version can be
 * cycled, compared, or edited while the drawer is open. There is no backdrop
 * and focus is not stolen, so no stray focus ring competes with the selection.
 */
function Drawer(props: DialogPrimitive.Root.Props) {
  return <DialogPrimitive.Root data-slot="drawer" {...props} />;
}

function DrawerContent({
  className,
  children,
  initialFocus = false,
  ...props
}: DialogPrimitive.Popup.Props) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Popup
        data-slot="drawer-content"
        initialFocus={initialFocus}
        className={cn(
          "fixed inset-y-0 right-0 z-50 flex h-dvh w-full max-w-md flex-col bg-card text-card-foreground shadow-xl ring-1 ring-foreground/10 outline-none duration-200 data-open:animate-in data-open:slide-in-from-right data-closed:animate-out data-closed:slide-out-to-right",
          className,
        )}
        {...props}
      >
        {children}
      </DialogPrimitive.Popup>
    </DialogPrimitive.Portal>
  );
}

export { Drawer, DrawerContent };
