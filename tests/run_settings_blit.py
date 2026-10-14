"""Compare Settings glyph/glow pixels against the pre-optimization renderer.

Run from a Visual Studio developer prompt. Uses the known baseline commit in
this fork, including fractional positions, clipping, opacity, and overlaps.
"""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
baseline = subprocess.check_output(
    ['git', 'show', '3291ca4:src/settings_text.cpp'], cwd=root).decode('utf-8')
current = (root/'src/settings_text.cpp').read_text(encoding='utf-8')
def functions(source):
    return source[source.index('inline float glyph_alpha4'):source.index('} // namespace')]

with tempfile.TemporaryDirectory(prefix='orb-settings-pixels-') as directory:
    work = Path(directory)
    source = r'''
#include <cmath>
#include <cstdint>
#include <cassert>
#include <vector>
#include <random>
#include <chrono>
#include <iostream>
constexpr int SCREEN_W=466, SCREEN_H=466;
using lv_opa_t = uint8_t;
struct lv_color_t { uint16_t full; };
'''
    for name, renderer in [('baseline', baseline), ('optimized', current)]:
        source += ('namespace '+name+' {\nlv_color_t *s_buf=nullptr;\n'
                   'constexpr int X_SAMPLE_CAPACITY=128;\n'
                   'int16_t s_xIndex[X_SAMPLE_CAPACITY];\n'
                   'float s_xFraction[X_SAMPLE_CAPACITY];\n'+functions(renderer)+'}\n')
    source += r'''
int main() {
    std::mt19937 rng(123456);
    std::vector<uint8_t> old(SCREEN_W*SCREEN_H*3), newer(old.size());
    baseline::s_buf=(lv_color_t*)old.data(); optimized::s_buf=(lv_color_t*)newer.data();
    for (int test=0; test<400; ++test) {
        int w=1+rng()%180, h=1+rng()%90;
        std::vector<uint8_t> glyph((w*h+1)/2);
        for (auto &p:glyph) p=uint8_t(rng());
        float x=float(int(rng()%566)-50)+float(rng()%256)/256;
        float y=float(int(rng()%566)-50)+float(rng()%256)/256;
        int glow=rng()%21; uint8_t opacity=uint8_t(rng());
        lv_color_t color{uint16_t(rng())}, glowColor{uint16_t(rng())};
        // Preserve accumulated background/overlap pixels across runs.
        baseline::blit_glyph_glow(glyph.data(),w,h,x,y,glowColor,glow,opacity);
        optimized::blit_glyph_glow(glyph.data(),w,h,x,y,glowColor,glow,opacity);
        baseline::blit_glyph(glyph.data(),w,h,x,y,color,opacity);
        optimized::blit_glyph(glyph.data(),w,h,x,y,color,opacity);
        assert(old==newer);
    }
    std::vector<uint8_t> narrow(6*32/2,0xAF);
    auto bench=[&](bool fast) {
        auto start=std::chrono::steady_clock::now();
        for(int i=0;i<500;++i) {
            if(fast) optimized::blit_glyph_glow(narrow.data(),6,32,233.3f,233.7f,{0xffff},8,255);
            else baseline::blit_glyph_glow(narrow.data(),6,32,233.3f,233.7f,{0xffff},8,255);
        }
        return std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
    };
    double before=bench(false), after=bench(true);
    std::cout<<"PASS: 400 byte-identical glyph/glow cases\n";
    std::cout<<"Host narrow-glyph benchmark: "<<before<<" ms -> "<<after<<" ms\n";
}
'''
    (work/'test.cpp').write_text(source, encoding='utf-8')
    subprocess.run(['cl','/nologo','/EHsc','/std:c++17','/O2','test.cpp','/Fe:test.exe'],cwd=work,check=True)
    subprocess.run([str(work/'test.exe')],cwd=work,check=True)
