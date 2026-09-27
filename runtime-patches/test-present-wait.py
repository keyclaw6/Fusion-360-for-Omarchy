#!/usr/bin/env python3
"""Compile actual Vulkan presentation helpers with sanitizer-backed host stubs."""
import argparse
from pathlib import Path
import subprocess
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--work-dir', required=True, type=Path, help='Completed build-overlay.py work directory')
base=parser.parse_args().work_dir.expanduser().resolve()
source=(base/'source/wine/dlls/win32u/vulkan.c').read_text()
def function(signature):
    start=source.index(signature)
    brace=source.index('{',start)
    level=1; end=brace+1
    while level:
        if source[end]=='{': level+=1
        elif source[end]=='}': level-=1
        end+=1
    return source[start:end]+'\n'
prelude=r'''
#define _GNU_SOURCE
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <pthread.h>
typedef int BOOL;
typedef int VkResult;
typedef unsigned long DWORD;
typedef uint32_t VkStructureType;
typedef struct VkBaseInStructure { VkStructureType sType; const struct VkBaseInStructure *pNext; } VkBaseInStructure;
#define TRUE 1
#define FALSE 0
#define VK_SUCCESS 0
#define VK_SUBOPTIMAL_KHR 1000001003
#define VK_TIMEOUT 2
#define VK_ERROR_DEVICE_LOST -4
#define VK_ERROR_OUT_OF_HOST_MEMORY -1
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PRESENT_WAIT_FEATURES_KHR 1
#define VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PRESENT_WAIT_2_FEATURES_KHR 2
#define VK_STRUCTURE_TYPE_PRESENT_ID_2_KHR 3
#define VK_STRUCTURE_TYPE_PRESENT_ID_KHR 4
#define VK_STRUCTURE_TYPE_PRESENT_WAIT_2_INFO_KHR 5
#define X11_PRESENT_WAIT_TIMEOUT_NS (1000 * 1000000ull)
typedef struct { VkStructureType sType; const void *pNext; BOOL presentWait; } VkPhysicalDevicePresentWaitFeaturesKHR;
typedef struct { VkStructureType sType; const void *pNext; BOOL presentWait2; } VkPhysicalDevicePresentWait2FeaturesKHR;
typedef struct { const void *pNext; } VkDeviceCreateInfo;
typedef struct { VkStructureType sType; const void *pNext; uint32_t swapchainCount; const uint64_t *pPresentIds; } VkPresentIdKHR;
typedef VkPresentIdKHR VkPresentId2KHR;
typedef struct { VkStructureType sType; const void *pNext; uint32_t flags; uint64_t presentId, timeout; } VkPresentWait2InfoKHR;
typedef uintptr_t VkSwapchainKHR;
typedef uintptr_t VkFence;
typedef uint32_t VkPresentModeKHR;
typedef struct { const void *pNext; uint32_t swapchainCount; const VkSwapchainKHR *pSwapchains; const uint32_t *pImageIndices; VkResult *pResults; } VkPresentInfoKHR;
#define VK_STRUCTURE_TYPE_DEVICE_GROUP_PRESENT_INFO_KHR 6
#define VK_STRUCTURE_TYPE_PRESENT_REGIONS_KHR 7
#define VK_STRUCTURE_TYPE_SWAPCHAIN_PRESENT_FENCE_INFO_KHR 8
#define VK_STRUCTURE_TYPE_SWAPCHAIN_PRESENT_MODE_INFO_KHR 9
typedef struct { VkStructureType sType; const void *pNext; uint32_t swapchainCount; const uint32_t *pDeviceMasks; } VkDeviceGroupPresentInfoKHR;
typedef struct { uint32_t rectangleCount; const void *pRectangles; } VkPresentRegionKHR;
typedef struct { VkStructureType sType; const void *pNext; uint32_t swapchainCount; const VkPresentRegionKHR *pRegions; } VkPresentRegionsKHR;
typedef struct { VkStructureType sType; const void *pNext; uint32_t swapchainCount; const VkFence *pFences; } VkSwapchainPresentFenceInfoKHR;
typedef struct { VkStructureType sType; const void *pNext; uint32_t swapchainCount; const VkPresentModeKHR *pPresentModes; } VkSwapchainPresentModeInfoKHR;
struct mempool { void *entries[64]; unsigned int count; };
static int pool_allocations, fail_pool_at, fail_host_malloc;
static void *mem_alloc(struct mempool *pool, size_t size) {
    if (++pool_allocations==fail_pool_at) return NULL;
    assert(pool->count<ARRAY_SIZE(pool->entries));
    void *p=calloc(1,size); assert(p); pool->entries[pool->count++]=p; return p;
}
static void pool_free(struct mempool *pool) { while(pool->count) free(pool->entries[--pool->count]); }
static void *host_malloc(size_t size) { if(fail_host_malloc) return NULL; return malloc(size); }
struct vulkan_queue { struct { uintptr_t queue; } host; };
static pthread_mutex_t producer_device_lock=PTHREAD_MUTEX_INITIALIZER;

struct vulkan_device {
    struct { uintptr_t device; } host;
    struct { BOOL has_VK_KHR_present_wait, has_VK_KHR_present_wait2; } extensions;
    VkResult (*p_vkQueuePresentKHR)(uintptr_t,const VkPresentInfoKHR*);
    VkResult (*p_vkWaitForPresentKHR)(uintptr_t,uintptr_t,uint64_t,uint64_t);
    VkResult (*p_vkWaitForPresent2KHR)(uintptr_t,uintptr_t,const VkPresentWait2InfoKHR*);
};
struct x11_present_device { struct vulkan_device obj; BOOL enabled, present_wait, present_wait2; };
struct client { int offscreen; };
struct surface { struct client *client; void *hwnd; };
struct swapchain {
    void *managed;
    BOOL x11_present_wait_disabled, x11_present_wait_retired, x11_present_wait_warned, x11_present_wait2;
    struct surface *surface;
    struct { struct { uintptr_t swapchain; } host; } obj;
    BOOL stale;
};
#define CONTAINING_RECORD(ptr,type,field) ((type*)((char*)(ptr)-offsetof(type,field)))
static int warnings, traces;
static void trace(const char *fmt,...) { (void)fmt; traces++; }
static void warn(const char *fmt,...) { (void)fmt; warnings++; }
#define TRACE_(x) trace
#define WARN_(x) warn
#define WARN warn
static const char *wine_dbgstr_longlong(uint64_t value) { (void)value; return "test-id"; }
static int InterlockedCompareExchange(int *p,int value,int cmp) { int old=*p; if (old==cmp) *p=value; return old; }
static BOOL swapchain_is_out_of_date(const struct swapchain *s) { return s->stale; }
static DWORD NtGetTickCount(void) { static DWORD tick; return tick+=17; }
static const void *find_next_struct(const VkBaseInStructure *header, VkStructureType type) {
    while(header) { if(header->sType==type) return header; header=header->pNext; } return NULL;
}
'''
actual=function('static struct x11_present_device *x11_present_device(')+function('static void init_x11_present_device(')+function('static void x11_wait_before_client_present(')+function('static void append_present_pnext(')+function('static VkResult repack_present_pnext(')

queue_start=source.index('static VkResult win32u_vkQueuePresentKHR(')
host_start=source.index('    if (host_count)',queue_start)
brace=source.index('{',host_start); end=brace+1; depth=1
while depth:
    if source[end]=='{': depth+=1
    elif source[end]=='}': depth-=1
    end+=1
host_body=source[host_start:end]
fixture=r'''
static int host_calls, require_submitted_ids;
static VkResult host_result;
static uint64_t submitted_ids[64];
static uint32_t submitted_count;
static VkResult host_present(uintptr_t queue,const VkPresentInfoKHR *info) {
    assert(queue==33); host_calls++;
    const VkPresentId2KHR *ids=find_next_struct(info->pNext,VK_STRUCTURE_TYPE_PRESENT_ID_2_KHR);
    submitted_count=ids ? ids->swapchainCount : 0;
    if(ids) {
        assert(ids->swapchainCount==info->swapchainCount && ids->swapchainCount<=64);
        for(uint32_t i=0;i<ids->swapchainCount;i++) submitted_ids[i]=ids->pPresentIds[i];
    }
    if(info->pResults) for(uint32_t i=0;i<info->swapchainCount;i++) info->pResults[i]=VK_SUCCESS;
    return host_result;
}
static BOOL actual_host_path(struct x11_present_device *d,struct swapchain *swapchain,
                             const VkPresentInfoKHR *original,const uint32_t *host_indices,uint32_t host_count) {
    VkPresentInfoKHR info=*original, *present_info=&info;
    struct vulkan_device *device=&d->obj;
    struct vulkan_queue queue_value={.host={33}}, *queue=&queue_value;
    VkSwapchainKHR host_handles[64], *swapchains=host_handles;
    struct mempool pool={0};
    VkResult res=VK_SUCCESS;
    BOOL host_present_succeeded=FALSE;
    for(uint32_t i=0;i<host_count;i++) host_handles[i]=22+i;
    device->p_vkQueuePresentKHR=host_present;
    #define malloc host_malloc
''' + host_body + r'''
    #undef malloc
    VkResult swapchain_res=present_info->pResults ? present_info->pResults[host_indices[0]] : res;
    x11_wait_before_client_present(device,swapchain,original,host_indices[0],host_present_succeeded,swapchain_res);
    pool_free(&pool);
    return host_present_succeeded;
}
'''
actual+=fixture
tests=r'''
static int calls1,calls2;
static uint64_t seen_id,seen_timeout;
static VkResult result;
static VkResult wait1(uintptr_t device,uintptr_t swapchain,uint64_t id,uint64_t timeout) {
    assert(device==11 && swapchain==22); calls1++; seen_id=id; seen_timeout=timeout; return result;
}
static VkResult wait2(uintptr_t device,uintptr_t swapchain,const VkPresentWait2InfoKHR *info) {
    assert(device==11 && swapchain==22);
    if(require_submitted_ids) { BOOL found=FALSE; for(uint32_t i=0;i<submitted_count;i++) if(submitted_ids[i]==info->presentId) found=TRUE; assert(found); }
    assert(info->sType==VK_STRUCTURE_TYPE_PRESENT_WAIT_2_INFO_KHR && !info->pNext && !info->flags);
    calls2++; seen_id=info->presentId; seen_timeout=info->timeout; return result;
}
int main(void) {
    struct x11_present_device d={0};
    struct client client={1};
    struct surface surface={&client,(void*)0x1234};
    struct swapchain s={0};
    uint64_t values[]={101,102};
    VkPresentIdKHR ids={VK_STRUCTURE_TYPE_PRESENT_ID_KHR,NULL,2,values};
    VkPresentId2KHR ids2={VK_STRUCTURE_TYPE_PRESENT_ID_2_KHR,&ids,2,values};
    VkPhysicalDevicePresentWaitFeaturesKHR feature={VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PRESENT_WAIT_FEATURES_KHR,NULL,1};
    VkPhysicalDevicePresentWait2FeaturesKHR feature2={VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PRESENT_WAIT_2_FEATURES_KHR,&feature,1};
    VkDeviceCreateInfo creation={&feature2};
    VkPresentInfoKHR info={.pNext=&ids};
    d.obj.host.device=11; d.obj.extensions.has_VK_KHR_present_wait=1; d.obj.extensions.has_VK_KHR_present_wait2=1;
    d.obj.p_vkWaitForPresentKHR=wait1; d.obj.p_vkWaitForPresent2KHR=wait2;
    s.surface=&surface; s.obj.host.swapchain=22;
    unsetenv("WINE_X11_VULKAN_PRESENT_WAIT");
    init_x11_present_device(&d,&creation); assert(!d.enabled);
    x11_wait_before_client_present(&d.obj,&s,&info,1,TRUE,VK_SUCCESS); assert(!calls1&&!calls2);
    setenv("WINE_X11_VULKAN_PRESENT_WAIT","0",1);
    init_x11_present_device(&d,&creation); assert(!d.enabled);
    setenv("WINE_X11_VULKAN_PRESENT_WAIT","1",1);
    init_x11_present_device(&d,&creation); assert(d.enabled&&d.present_wait&&d.present_wait2);
    x11_wait_before_client_present(&d.obj,&s,&info,1,TRUE,VK_SUCCESS);
    assert(calls1==1&&!calls2&&seen_id==102&&seen_timeout==1000000000ull&&!s.x11_present_wait_disabled);
    x11_wait_before_client_present(&d.obj,&s,&info,1,FALSE,VK_SUCCESS); assert(calls1==1&&!calls2);
    // Onscreen, managed, errored, retired, stale and missing surfaces must not wait.
    client.offscreen=0; x11_wait_before_client_present(&d.obj,&s,&info,0,TRUE,VK_SUCCESS); client.offscreen=1;
    s.managed=(void*)1; x11_wait_before_client_present(&d.obj,&s,&info,0,TRUE,VK_SUCCESS); s.managed=NULL;
    x11_wait_before_client_present(&d.obj,&s,&info,0,TRUE,VK_ERROR_DEVICE_LOST);
    s.x11_present_wait_retired=1; x11_wait_before_client_present(&d.obj,&s,&info,0,TRUE,VK_SUCCESS); s.x11_present_wait_retired=0;
    s.stale=1; x11_wait_before_client_present(&d.obj,&s,&info,0,TRUE,VK_SUCCESS); s.stale=0;
    s.surface=NULL; x11_wait_before_client_present(&d.obj,&s,&info,0,TRUE,VK_SUCCESS); s.surface=&surface;
    surface.client=NULL; x11_wait_before_client_present(&d.obj,&s,&info,0,TRUE,VK_SUCCESS); surface.client=&client;
    assert(calls1==1&&!calls2);
    // Unsupported and zero/missing IDs do not call Vulkan; an initial probe without ID may recover.
    d.present_wait=0; x11_wait_before_client_present(&d.obj,&s,&info,0,TRUE,VK_SUCCESS); assert(calls1==1&&warnings==1);
    d.present_wait=1; values[0]=0; x11_wait_before_client_present(&d.obj,&s,&info,0,TRUE,VK_SUCCESS); assert(calls1==1&&warnings==1);
    x11_wait_before_client_present(&d.obj,&s,&info,2,TRUE,VK_SUCCESS); assert(calls1==1);
    values[0]=101; x11_wait_before_client_present(&d.obj,&s,&info,0,TRUE,VK_SUCCESS); assert(calls1==2&&seen_id==101);
    d.obj.extensions.has_VK_KHR_present_wait=0; x11_wait_before_client_present(&d.obj,&s,&info,0,TRUE,VK_SUCCESS); d.obj.extensions.has_VK_KHR_present_wait=1;
    d.obj.p_vkWaitForPresentKHR=NULL; x11_wait_before_client_present(&d.obj,&s,&info,0,TRUE,VK_SUCCESS); d.obj.p_vkWaitForPresentKHR=wait1;
    assert(calls1==2);
    // wait2 additionally requires the swapchain capability flag; it may fall back only to a supplied v1 ID.
    info.pNext=&ids2; x11_wait_before_client_present(&d.obj,&s,&info,1,TRUE,VK_SUCCESS); assert(calls1==3&&!calls2);
    s.x11_present_wait2=1; x11_wait_before_client_present(&d.obj,&s,&info,1,TRUE,VK_SUCCESS); assert(calls2==1&&seen_id==102&&seen_timeout==1000000000ull);
    d.present_wait2=0; ids2.pNext=NULL; x11_wait_before_client_present(&d.obj,&s,&info,1,TRUE,VK_SUCCESS); assert(calls2==1&&calls1==3);
    d.present_wait2=1; d.obj.extensions.has_VK_KHR_present_wait2=0; x11_wait_before_client_present(&d.obj,&s,&info,1,TRUE,VK_SUCCESS); assert(calls2==1);
    d.obj.extensions.has_VK_KHR_present_wait2=1; d.obj.p_vkWaitForPresent2KHR=NULL; x11_wait_before_client_present(&d.obj,&s,&info,1,TRUE,VK_SUCCESS); assert(calls2==1);
    d.obj.p_vkWaitForPresent2KHR=wait2;
    // One finite timed-out call disables this swapchain; no repeated one-second stalls.
    result=VK_TIMEOUT; x11_wait_before_client_present(&d.obj,&s,&info,0,TRUE,VK_SUCCESS);
    assert(calls2==2&&s.x11_present_wait_disabled&&seen_timeout==1000000000ull);
    x11_wait_before_client_present(&d.obj,&s,&info,0,TRUE,VK_SUCCESS); assert(calls2==2);
    s.x11_present_wait_disabled=0; result=VK_ERROR_DEVICE_LOST;
    x11_wait_before_client_present(&d.obj,&s,&info,0,TRUE,VK_SUCCESS); assert(calls2==3&&s.x11_present_wait_disabled);
    s.x11_present_wait_disabled=0; result=VK_SUBOPTIMAL_KHR;
    x11_wait_before_client_present(&d.obj,&s,&info,0,TRUE,VK_SUBOPTIMAL_KHR); assert(calls2==4&&!s.x11_present_wait_disabled);
    // Actual enabled-feature chain is honored, not merely advertised device extension bits.
    creation.pNext=NULL; init_x11_present_device(&d,&creation); assert(d.enabled&&!d.present_wait&&!d.present_wait2);
    x11_wait_before_client_present(&d.obj,&s,&info,0,TRUE,VK_SUCCESS); assert(calls2==4);

    // Exercise actual mixed host/managed repacking + submission + wait, not synthetic ID stubs.
    {
        uint64_t mixed_ids[18]; uint32_t indices[18], host_indices[17]; VkSwapchainKHR handles[18]; VkResult results[18]={0};
        for(uint32_t i=0;i<18;i++) { mixed_ids[i]=500+i; indices[i]=i; handles[i]=22+i; if(i<17) host_indices[i]=i+1; }
        VkPresentId2KHR mixed={VK_STRUCTURE_TYPE_PRESENT_ID_2_KHR,NULL,3,mixed_ids};
        VkPresentInfoKHR mixed_info={.pNext=&mixed,.swapchainCount=3,.pSwapchains=handles,.pImageIndices=indices,.pResults=results};
        creation.pNext=&feature2; init_x11_present_device(&d,&creation);
        result=VK_SUCCESS; s.x11_present_wait_disabled=0; s.x11_present_wait2=1;
        pool_allocations=0; host_result=VK_SUCCESS; require_submitted_ids=1;
        int before=calls2;
        assert(actual_host_path(&d,&s,&mixed_info,host_indices,2));
        assert(host_calls==1 && submitted_count==2 && submitted_ids[0]==501 && submitted_ids[1]==502);
        assert(calls2==before+1 && seen_id==501);
        // Caller pResults remain zero if allocating/repacking fails; that does not mean submission happened.
        pool_allocations=0; fail_pool_at=1; before=calls2;
        assert(!actual_host_path(&d,&s,&mixed_info,host_indices,2));
        assert(host_calls==1 && calls2==before && !s.x11_present_wait_disabled);
        fail_pool_at=0; fail_host_malloc=1; mixed.swapchainCount=18; mixed_info.swapchainCount=18;
        assert(!actual_host_path(&d,&s,&mixed_info,host_indices,17));
        assert(host_calls==1 && calls2==before && !s.x11_present_wait_disabled);
        fail_host_malloc=0; pool_allocations=0; mixed.swapchainCount=3; mixed_info.swapchainCount=3;
        // A called but failed host present must not authorize waits from stale successful pResults either.
        host_result=VK_ERROR_DEVICE_LOST;
        assert(!actual_host_path(&d,&s,&mixed_info,host_indices,2));
        assert(host_calls==2 && calls2==before && !s.x11_present_wait_disabled);
        require_submitted_ids=0;
    }
    puts("PASS: feature/ID selection, index bounds, opt-in/offscreen gates, wait2 capabilities, finite timeout, failure disablement, actual mixed-ID2 host repacking and pre-submit allocation failures");
    return 0;
}
'''
path=base/'test-present-wait.c'
path.write_text(prelude+actual+tests)
# The real call is after host queue submission, outside its mutex, immediately before parent copy.
needle='x11_wait_before_client_present( device, swapchain, client_present_info, i, host_present_succeeded, swapchain_res );\n            client_surface_present( surface->client );'
assert needle in source
assert source.index('res = device->p_vkQueuePresentKHR( queue->host.queue, &host_info );')<source.index(needle)
subprocess.run(['cc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(path),'-o',str(base/'test-present-wait')],check=True)
subprocess.run([str(base/'test-present-wait')],check=True)
