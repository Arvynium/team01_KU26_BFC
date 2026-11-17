cmake_minimum_required(VERSION 3.16)
project(BFC_Proj VERSION 0.1.0 LANGUAGES C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_C_EXTENSIONS OFF)

if(NOT CMAKE_SYSTEM_NAME STREQUAL "Linux" OR
   NOT CMAKE_C_COMPILER_ID MATCHES "GNU|Clang")
    message(FATAL_ERROR "This exercise targets Linux with GCC or Clang.")
endif()

# Apply the exercise settings to both our code and the bundled static library.
add_compile_options(-O0 -g -fno-stack-protector -fno-pie
                    -fno-omit-frame-pointer -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=0)
add_link_options(-no-pie -Wl,-z,noexecstack -Wl,-z,relro -Wl,-z,lazy)

set(EXPAT_SHARED_LIBS OFF CACHE BOOL "" FORCE)
set(EXPAT_BUILD_TOOLS OFF CACHE BOOL "" FORCE)
set(EXPAT_BUILD_EXAMPLES OFF CACHE BOOL "" FORCE)
set(EXPAT_BUILD_TESTS OFF CACHE BOOL "" FORCE)
set(EXPAT_BUILD_DOCS OFF CACHE BOOL "" FORCE)
set(EXPAT_BUILD_PKGCONFIG OFF CACHE BOOL "" FORCE)
set(EXPAT_ENABLE_INSTALL OFF CACHE BOOL "" FORCE)
set(EXPAT_DTD ON CACHE BOOL "" FORCE)
set(EXPAT_NS ON CACHE BOOL "" FORCE)
add_subdirectory(third_party/libexpat/expat EXCLUDE_FROM_ALL)

find_package(Threads REQUIRED)
add_executable(bfc src/main.c src/menu.c src/input.c src/document.c src/file.c src/parser.c
                   src/summary.c src/refund.c src/buy.c src/review.c)
target_include_directories(bfc PRIVATE include)
# _DEFAULT_SOURCE exposes usleep on glibc alongside the POSIX interfaces.
target_compile_definitions(bfc PRIVATE _POSIX_C_SOURCE=200809L _DEFAULT_SOURCE)
target_compile_options(bfc PRIVATE -Wall -Wextra -Wpedantic)
target_link_libraries(bfc PRIVATE expat Threads::Threads)
