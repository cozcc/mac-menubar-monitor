#import <Cocoa/Cocoa.h>
#import <mach/mach.h>
#import <mach/mach_host.h>
#import <sys/sysctl.h>

typedef struct {
    uint64_t user;
    uint64_t system;
    uint64_t idle;
    uint64_t nice;
} CPUCounter;

typedef struct {
    BOOL hasCPUPercent;
    double cpuPercent;
    BOOL hasMemory;
    uint64_t memoryUsedBytes;
    uint64_t memoryTotalBytes;
} SystemSnapshot;

@interface SystemSampler : NSObject
@property(nonatomic) BOOL hasPreviousCPUCounter;
@property(nonatomic) CPUCounter previousCPUCounter;
- (SystemSnapshot)snapshot;
@end

@implementation SystemSampler

- (SystemSnapshot)snapshot {
    SystemSnapshot snapshot = {0};

    CPUCounter currentCPUCounter = {0};
    BOOL hasCurrentCPUCounter = [self readCPUCounter:&currentCPUCounter];
    if (hasCurrentCPUCounter && self.hasPreviousCPUCounter) {
        uint64_t previousTotal = [self totalTicks:self.previousCPUCounter];
        uint64_t currentTotal = [self totalTicks:currentCPUCounter];
        uint64_t totalDelta = currentTotal >= previousTotal ? currentTotal - previousTotal : 0;
        uint64_t idleDelta = currentCPUCounter.idle >= self.previousCPUCounter.idle
            ? currentCPUCounter.idle - self.previousCPUCounter.idle
            : 0;

        if (totalDelta > 0) {
            double busy = 1.0 - ((double)idleDelta / (double)totalDelta);
            snapshot.cpuPercent = fmax(0.0, fmin(100.0, busy * 100.0));
            snapshot.hasCPUPercent = YES;
        }
    }

    if (hasCurrentCPUCounter) {
        self.previousCPUCounter = currentCPUCounter;
        self.hasPreviousCPUCounter = YES;
    }

    uint64_t usedBytes = 0;
    uint64_t totalBytes = 0;
    if ([self readMemoryUsedBytes:&usedBytes totalBytes:&totalBytes]) {
        snapshot.memoryUsedBytes = usedBytes;
        snapshot.memoryTotalBytes = totalBytes;
        snapshot.hasMemory = YES;
    }

    return snapshot;
}

- (uint64_t)totalTicks:(CPUCounter)counter {
    return counter.user + counter.system + counter.idle + counter.nice;
}

- (BOOL)readCPUCounter:(CPUCounter *)counter {
    natural_t processorCount = 0;
    processor_info_array_t processorInfo = NULL;
    mach_msg_type_number_t processorInfoCount = 0;

    kern_return_t result = host_processor_info(
        mach_host_self(),
        PROCESSOR_CPU_LOAD_INFO,
        &processorCount,
        &processorInfo,
        &processorInfoCount
    );

    if (result != KERN_SUCCESS || processorInfo == NULL) {
        return NO;
    }

    processor_cpu_load_info_t loadInfo = (processor_cpu_load_info_t)processorInfo;
    CPUCounter nextCounter = {0};

    for (natural_t index = 0; index < processorCount; index++) {
        nextCounter.user += loadInfo[index].cpu_ticks[CPU_STATE_USER];
        nextCounter.system += loadInfo[index].cpu_ticks[CPU_STATE_SYSTEM];
        nextCounter.idle += loadInfo[index].cpu_ticks[CPU_STATE_IDLE];
        nextCounter.nice += loadInfo[index].cpu_ticks[CPU_STATE_NICE];
    }

    vm_deallocate(
        mach_task_self(),
        (vm_address_t)processorInfo,
        (vm_size_t)processorInfoCount * sizeof(integer_t)
    );

    *counter = nextCounter;
    return YES;
}

- (BOOL)readMemoryUsedBytes:(uint64_t *)usedBytes totalBytes:(uint64_t *)totalBytes {
    vm_statistics64_data_t stats;
    mach_msg_type_number_t statsCount = HOST_VM_INFO64_COUNT;

    kern_return_t statsResult = host_statistics64(
        mach_host_self(),
        HOST_VM_INFO64,
        (host_info64_t)&stats,
        &statsCount
    );

    if (statsResult != KERN_SUCCESS) {
        return NO;
    }

    vm_size_t pageSize = 0;
    if (host_page_size(mach_host_self(), &pageSize) != KERN_SUCCESS) {
        return NO;
    }

    uint64_t total = 0;
    size_t totalSize = sizeof(total);
    if (sysctlbyname("hw.memsize", &total, &totalSize, NULL, 0) != 0 || total == 0) {
        return NO;
    }

    uint64_t usedPages = stats.active_count + stats.wire_count + stats.compressor_page_count;
    uint64_t used = usedPages * (uint64_t)pageSize;
    if (used > total) {
        used = total;
    }

    *usedBytes = used;
    *totalBytes = total;
    return YES;
}

@end

@interface AppDelegate : NSObject <NSApplicationDelegate>
@property(nonatomic, strong) SystemSampler *sampler;
@property(nonatomic, strong) NSStatusItem *statusItem;
@property(nonatomic, strong) NSMenuItem *detailsItem;
@property(nonatomic, strong) NSTimer *timer;
@end

@implementation AppDelegate

- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    (void)notification;

    self.sampler = [SystemSampler new];
    self.statusItem = [[NSStatusBar systemStatusBar] statusItemWithLength:NSVariableStatusItemLength];
    self.statusItem.button.font = [NSFont monospacedDigitSystemFontOfSize:12.0 weight:NSFontWeightMedium];
    self.statusItem.button.toolTip = @"天元模型控制台 CPU/MEM";

    self.detailsItem = [[NSMenuItem alloc] initWithTitle:@"正在读取..." action:nil keyEquivalent:@""];
    self.detailsItem.enabled = NO;

    NSMenuItem *openItem = [[NSMenuItem alloc] initWithTitle:@"打开天元模型控制台" action:@selector(openConsole) keyEquivalent:@"o"];
    openItem.target = self;

    NSMenuItem *refreshItem = [[NSMenuItem alloc] initWithTitle:@"刷新" action:@selector(refresh) keyEquivalent:@"r"];
    refreshItem.target = self;

    NSMenuItem *quitItem = [[NSMenuItem alloc] initWithTitle:@"退出菜单栏显示" action:@selector(quit) keyEquivalent:@"q"];
    quitItem.target = self;

    NSMenu *menu = [NSMenu new];
    [menu addItem:self.detailsItem];
    [menu addItem:[NSMenuItem separatorItem]];
    [menu addItem:openItem];
    [menu addItem:refreshItem];
    [menu addItem:[NSMenuItem separatorItem]];
    [menu addItem:quitItem];
    self.statusItem.menu = menu;

    [self refresh];
    self.timer = [NSTimer scheduledTimerWithTimeInterval:2.0 target:self selector:@selector(refresh) userInfo:nil repeats:YES];
}

- (void)refresh {
    SystemSnapshot snapshot = [self.sampler snapshot];
    self.statusItem.button.title = [self menuTitleForSnapshot:snapshot];
    self.detailsItem.title = [self detailTitleForSnapshot:snapshot];
}

- (void)openConsole {
    NSURL *url = [NSURL URLWithString:@"http://127.0.0.1:51280/"];
    if (url != nil) {
        [[NSWorkspace sharedWorkspace] openURL:url];
    }
}

- (void)quit {
    [self.timer invalidate];
    [NSApp terminate:nil];
}

- (NSString *)menuTitleForSnapshot:(SystemSnapshot)snapshot {
    NSString *cpu = snapshot.hasCPUPercent
        ? [NSString stringWithFormat:@"CPU %.0f%%", snapshot.cpuPercent]
        : @"CPU --%";

    NSString *memory = @"MEM --%";
    if (snapshot.hasMemory && snapshot.memoryTotalBytes > 0) {
        double memoryPercent = (double)snapshot.memoryUsedBytes / (double)snapshot.memoryTotalBytes * 100.0;
        memory = [NSString stringWithFormat:@"MEM %.0f%%", memoryPercent];
    }

    return [NSString stringWithFormat:@"%@  %@", cpu, memory];
}

- (NSString *)detailTitleForSnapshot:(SystemSnapshot)snapshot {
    NSString *cpu = snapshot.hasCPUPercent
        ? [NSString stringWithFormat:@"CPU: %.1f%%", snapshot.cpuPercent]
        : @"CPU: calculating...";

    if (!snapshot.hasMemory || snapshot.memoryTotalBytes == 0) {
        return [NSString stringWithFormat:@"%@ | MEM: unavailable", cpu];
    }

    double memoryPercent = (double)snapshot.memoryUsedBytes / (double)snapshot.memoryTotalBytes * 100.0;
    return [NSString stringWithFormat:@"%@ | MEM: %@ / %@ (%.1f%%)",
        cpu,
        [self formatBytes:snapshot.memoryUsedBytes],
        [self formatBytes:snapshot.memoryTotalBytes],
        memoryPercent
    ];
}

- (NSString *)formatBytes:(uint64_t)bytes {
    double gib = (double)bytes / 1073741824.0;
    return [NSString stringWithFormat:@"%.1f GB", gib];
}

@end

static AppDelegate *sharedAppDelegate = nil;

int main(int argc, const char *argv[]) {
    (void)argc;
    (void)argv;

    @autoreleasepool {
        NSApplication *application = [NSApplication sharedApplication];
        [application setActivationPolicy:NSApplicationActivationPolicyAccessory];

        sharedAppDelegate = [AppDelegate new];
        application.delegate = sharedAppDelegate;
        [application run];
    }

    return 0;
}
