cmake_minimum_required(VERSION 3.15...3.26)
project(${SKBUILD_PROJECT_NAME} LANGUAGES C)

find_package(
    Python
    COMPONENTS Development.Module
    REQUIRED)

python_add_library(stsp MODULE stsp/ src/stsp.c WITH_SOABI)
add_executable(stsp_executable src/stsp.c)

target_link_libraries(stsp PRIVATE m)
target_link_libraries(stsp_executable PRIVATE m)

install(TARGETS stsp DESTINATION ${SKBUILD_PROJECT_NAME})
install(TARGETS stsp_executable RUNTIME DESTINATION ${SKBUILD_PROJECT_NAME})
