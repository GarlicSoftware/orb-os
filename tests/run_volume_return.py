"""Exercise the actual volume-save branch with persistence/UI stubs.

Run from a Visual Studio developer prompt: python tests/run_volume_return.py
"""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root/'src/settings_view.cpp').read_text(encoding='utf-8')
press = source[source.index('void settingsview::onPress()'):]
body = press.split('} else if (s_mode == MODE_VOLUME) {',1)[1].split('} else if (s_mode == MODE_LOCATION)',1)[0]
with tempfile.TemporaryDirectory(prefix='orb-volume-test-') as directory:
    work = Path(directory)
    test = r'''
#include <cassert>
#include <iostream>
enum { VOL_MASTER, VOL_TICK, VOL_CHIME };
enum { MODE_VOLUME, MODE_SOUND };
int s_volTarget, s_vol, page, savedTarget, savedLevel, saveCalls, previewCalls;
bool captured=true, browsing=false;
void save(int target,int level,bool persist) {
    assert(persist); savedTarget=target; savedLevel=level; ++saveCalls;
}
void host_set_tick_volume(int v,bool p) { save(VOL_TICK,v,p); }
void host_set_chime_volume(int v,bool p) { save(VOL_CHIME,v,p); }
void host_set_volume(int v,bool p) { save(VOL_MASTER,v,p); }
void host_sound_preview_beep() { ++previewCalls; }
void show_page(int p) { page=p; }
namespace app_shell {
void setCaptured(bool c) { captured=c; }
void openSwitcher() { browsing=true; }
}
void volume_press() {
'''+body+r'''
}
int main() {
    for(int target:{VOL_MASTER,VOL_TICK,VOL_CHIME}) for(int value:{0,50,100}) {
        s_volTarget=target; s_vol=value; page=MODE_VOLUME;
        captured=true; browsing=false; saveCalls=previewCalls=0;
        volume_press();
        assert(page==MODE_SOUND && captured && !browsing);
        assert(saveCalls==1 && savedTarget==target && savedLevel==value);
        assert(previewCalls==(target==VOL_MASTER ? 1 : 0));
    }
    std::cout<<"PASS: all three volume targets save and return to Sound\n";
}
'''
    (work/'test.cpp').write_text(test,encoding='utf-8')
    subprocess.run(['cl','/nologo','/EHsc','/std:c++17','test.cpp','/Fe:test.exe'],cwd=work,check=True)
    subprocess.run([str(work/'test.exe')],cwd=work,check=True)
