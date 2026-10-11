"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import {
  getPackagingListing,
  generatePackagingListing,
  type PackagingBrief,
} from "@/lib/packaging";

export function usePackagingListing(projectId: string) {
  const client = useQueryClient();
  const queryKey = ["packaging-listing", projectId];
  const listing = useQuery({
    queryKey,
    queryFn: () => getPackagingListing(projectId),
    staleTime: 0,
    refetchInterval: (query) =>
      query.state.data?.status === "queued" ||
      query.state.data?.status === "generating"
        ? 3000
        : false,
  });
  const generate = useMutation({
    mutationFn: (brief: PackagingBrief) =>
      generatePackagingListing(projectId, brief),
    onSuccess: () => client.invalidateQueries({ queryKey }),
    onError: (error) => toast.error(error.message),
  });
  const busy =
    generate.isPending ||
    listing.data?.status === "queued" ||
    listing.data?.status === "generating";
  return { listing, generate, busy };
}
